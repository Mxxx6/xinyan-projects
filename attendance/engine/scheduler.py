"""定时任务调度 — 按时段检查所有班级"""

import logging
from datetime import datetime, timedelta, date
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import load_config
from dingtalk import fetch_attendance_records, fetch_students_by_dept
from dingtalk.auth import get_access_token
from notify.dispatcher import dispatch_all
from db.models import db_session
from engine.rules import classify_status, generate_report

logger = logging.getLogger("attendance.scheduler")

_scheduler: Optional[BackgroundScheduler] = None
_job_status: dict = {}

# dept_id → dept_name 缓存
_dept_names: dict = {}


def _build_trigger(weekdays: list[int], time_str: str, notify_after: int) -> CronTrigger:
    hour, minute = map(int, time_str.split(":"))
    notify_dt = datetime(2000, 1, 1, hour, minute) + timedelta(minutes=notify_after)
    return CronTrigger(
        day_of_week=",".join(str(d) for d in weekdays),
        hour=notify_dt.hour,
        minute=notify_dt.minute,
    )


def run_attendance_check(schedule_config: dict, config: Optional[dict] = None,
                        override_date: str = "", override_dept_ids: list = None):
    if config is None:
        config = load_config()

    slot_name = schedule_config["name"]
    time_str = schedule_config["time"]
    dept_ids = override_dept_ids if override_dept_ids else schedule_config["dept_ids"]
    rules_cfg = config["rules"]
    early_min = rules_cfg["early_minutes"]
    late_grace = rules_cfg["late_grace_minutes"]

    # 构建 dept_id → dept_name 映射
    global _dept_names
    dept_labels = config.get("dept_labels", {})
    for did in dept_ids:
        if did not in _dept_names:
            _dept_names[did] = dept_labels.get(did, f"部门{did}")

    if override_date:
        target_date = datetime.strptime(override_date, "%Y-%m-%d").date()
    else:
        target_date = date.today()
    deadline = datetime.combine(target_date, datetime.strptime(time_str, "%H:%M").time())
    date_str = target_date.strftime("%Y-%m-%d")

    logger.info(f"⏰ 考勤: {slot_name} ({date_str} {time_str}, {len(dept_ids)}部门)")

    try:
        dcfg = config["dingtalk"]
        token = get_access_token(dcfg["app_key"], dcfg["app_secret"])

        # 收集所有部门学生，按 user_id 去重（保留第一个出现的部门）
        all_students: dict[str, dict] = {}
        for dept_id in dept_ids:
            dept_name = _dept_names.get(dept_id, f"部门{dept_id}")
            students = fetch_students_by_dept(token, dept_id, dept_name)
            for s in students:
                if s["user_id"] not in all_students:
                    all_students[s["user_id"]] = s

        student_list = list(all_students.values())
        logger.info(f"👥 去重后 {len(student_list)} 名学生（仅工号）")

        if not student_list:
            _job_status[slot_name] = {
                "last_run": datetime.now().strftime("%H:%M:%S"),
                "last_result": "⚠️ 无学生", "report": "",
            }
            return

        # 拉取简道云请假数据
        from dingtalk.jiandaoyun import get_leave_users
        leave_out, leave_in = get_leave_users(date_str)
        slot_label = _slot_label(deadline.hour)
        leave_out_set = {xh for xh, slots in leave_out.items() if slot_label in slots}
        leave_in_set = {xh for xh, slots in leave_in.items() if slot_label in slots}
        if leave_out_set or leave_in_set:
            logger.info(f"📝 简道云请假({slot_label}): 外出{len(leave_out_set)} 在校{len(leave_in_set)}")

        # 拉取打卡
        records = fetch_attendance_records(
            token, dept_ids[0], deadline,
            deadline + timedelta(hours=2),
            students=student_list,
        )

        # 按时段过滤打卡：只取该时段窗口内的记录
        slot_hour = deadline.hour
        if slot_hour < 11:
            window_start = 6
            window_end = 12
        elif slot_hour < 16:
            window_start = 12
            window_end = 17
        else:
            window_start = 17
            window_end = 23

        record_map: dict[str, dict] = {}
        for r in records:
            uid = r["user_id"]
            ct = r["check_in_time"]
            try:
                ch = int(ct[11:13])
                if not (window_start <= ch < window_end):
                    continue
            except:
                continue
            if uid not in record_map or ct < record_map[uid]["check_in_time"]:
                record_map[uid] = r

        results = []
        for s in student_list:
            rec = record_map.get(s["user_id"])
            check_in = rec["check_in_time"] if rec else None
            is_makeup = rec.get("is_makeup", False) if rec else False
            makeup_time = rec.get("makeup_time", "") if rec else ""

            time_result = rec.get("time_result", "") if rec else ""
            status, label = classify_status(
                check_in, time_result,
                deadline=deadline,
                early_minutes=early_min,
                late_grace_minutes=late_grace,
            )
            # 简道云请假：按学号(job_number)匹配，校内优先
            jn = s.get("job_number", "")
            if jn in leave_in_set:
                status, label = "leave_in", "🏫 在校请假"
                check_in = None
            elif jn in leave_out_set:
                status, label = "leave_out", "🚶 外出请假"
                check_in = None
            results.append({
                "student_user_id": s["user_id"],
                "student_name": s["name"],
                "job_number": s.get("job_number", ""),
                "dept_name": s.get("dept_name", ""),
                "check_in_time": check_in,
                "is_makeup": is_makeup,
                "makeup_time": makeup_time,
                "status": status,
                "label": label,
            })

        # 报告
        report = generate_report(slot_name, date_str, time_str, results)

        # 存 DB（先清除该日期该时段的旧记录，避免重复）
        with db_session() as conn:
            conn.execute("DELETE FROM attendance_records WHERE class_name=? AND class_date=?", (slot_name, date_str))
            for r in results:
                conn.execute(
                    """INSERT INTO attendance_records
                       (class_name, class_date, class_start_time,
                        student_name, student_user_id, check_in_time,
                        status, department, job_number)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (slot_name, date_str, time_str,
                     r["student_name"], r["student_user_id"],
                     r["check_in_time"], r["status"],
                     r["dept_name"], r["job_number"])
                )

        # 推送
        dispatch_all(slot_name, report, config.get("notify", {}))

        with db_session() as conn:
            conn.execute(
                "INSERT INTO notify_logs (class_name, channel, content, success) VALUES (?, ?, ?, 1)",
                (slot_name, "all", report)
            )

        _job_status[slot_name] = {
            "last_run": datetime.now().strftime("%H:%M:%S"),
            "last_result": "✅ 成功", "report": report,
        }
        logger.info(f"✅ {slot_name} 完成")

    except Exception as e:
        _job_status[slot_name] = {
            "last_run": datetime.now().strftime("%H:%M:%S"),
            "last_result": f"❌ {e}", "report": "",
        }
        logger.error(f"❌ {slot_name} 失败: {e}", exc_info=True)


def start_scheduler(config: Optional[dict] = None):
    global _scheduler, _dept_names
    if _scheduler is not None:
        return
    if config is None:
        config = load_config()

    # 预加载部门名称映射
    dept_labels = config.get("dept_labels", {})
    for did in dept_labels:
        _dept_names[did] = dept_labels[did]

    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai", job_defaults={"misfire_grace_time": 300})

    for slot in config.get("schedule", []):
        trigger = _build_trigger(slot["weekdays"], slot["time"], slot["notify_after_minutes"])
        _scheduler.add_job(
            run_attendance_check, trigger=trigger,
            args=[slot, config], id=slot["name"], name=slot["name"],
            replace_existing=True,
        )
        days = ",".join(str(d) for d in slot["weekdays"])
        logger.info(f"📅 {slot['name']} — 周{days} {slot['time']} (+{slot['notify_after_minutes']}min)")

    _scheduler.start()
    logger.info("🚀 调度器已启动")


def _slot_label(hour: int) -> str:
    if 6 <= hour < 12: return "上午"
    elif 12 <= hour < 17: return "下午"
    else: return "晚上"


def check_schedule_status() -> list[dict]:
    jobs = []
    if _scheduler:
        for job in _scheduler.get_jobs():
            s = _job_status.get(job.id, {})
            jobs.append({
                "name": job.id,
                "next_run": job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else "N/A",
                "last_run": s.get("last_run", "未触发"),
                "last_result": s.get("last_result", "-"),
            })
    return jobs


def get_dept_names() -> dict:
    return _dept_names
