"""Web路由 — 页面 + API"""

import csv
import io
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Request, Query, Response
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse

def _time_to_slot(time_str: str) -> str:
    """将时间映射到考勤时段"""
    if not time_str:
        return ""
    try:
        h = int(time_str.split(":")[0])
    except:
        return ""
    if 6 <= h < 12:
        return "上午"
    elif 12 <= h < 17:
        return "下午"
    else:
        return "晚上"


from config import load_config
from db.models import db_session
from engine.rules import STATUS_LABELS, STATUS_ORDER
from engine.scheduler import run_attendance_check, check_schedule_status, _job_status


def _dept_id_to_name(dept_id: str) -> str:
    """部门ID转名称，用于筛选"""
    if not dept_id:
        return ""
    config = load_config()
    labels = config.get("dept_labels", {})
    return labels.get(int(dept_id), dept_id)

router = APIRouter()
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# ── helpers ──

def _get_today_classes(config: dict) -> list[dict]:
    today = date.today()
    today_weekday = today.weekday()
    now = datetime.now()
    classes = []
    for cls in config.get("schedule", []):
        weekdays = cls.get("weekdays", [cls.get("weekday", -1)])
        if today_weekday not in weekdays:
            continue
        hour, minute = map(int, cls["time"].split(":"))
        notify_after = cls.get("notify_after_minutes", 5)
        notify_dt = datetime(2000, 1, 1, hour, minute) + timedelta(minutes=notify_after)
        class_start = datetime.combine(today, datetime.strptime(cls["time"], "%H:%M").time())
        with db_session() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM attendance_records WHERE class_name=? AND class_date=?",
                (cls["name"], today.strftime("%Y-%m-%d"))
            ).fetchone()
        checked = row["cnt"] > 0 if row else False
        classes.append({
            "name": cls["name"], "time": cls["time"],
            "notify_time": f"{notify_dt.hour:02d}:{notify_dt.minute:02d}",
            "checked": checked,
            "pending": class_start <= now and not checked,
        })
    return classes


def _query_records(class_name: str = "", date_from: str = "", date_to: str = "",
                   status: str = "", department: str = "", departments: list = None, limit: int = 5000) -> list[dict]:
    """通用出勤记录查询，支持筛选"""
    sql = """SELECT class_name, class_date, class_start_time,
                    student_name, student_user_id, check_in_time, status,
                    department, job_number, manual_note, created_at
             FROM attendance_records WHERE 1=1"""
    params = []

    if class_name:
        sql += " AND class_name = ?"
        params.append(class_name)
    if date_from:
        sql += " AND class_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND class_date <= ?"
        params.append(date_to)
    if status:
        sql += " AND status = ?"
        params.append(status)
    if department:
        sql += " AND department = ?"
        params.append(department)
    if departments:
        placeholders = ",".join("?" * len(departments))
        sql += f" AND department IN ({placeholders})"
        params.extend(departments)

    sql += """ ORDER BY
        CASE status WHEN 'absent' THEN 1 WHEN 'leave' THEN 2
                    WHEN 'late_long' THEN 3 WHEN 'late' THEN 4 ELSE 5 END,
        created_at DESC
        LIMIT ?"""
    params.append(limit)

    with db_session() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [
        {
            "class_name": r["class_name"], "class_date": r["class_date"],
            "class_start_time": r["class_start_time"],
            "student_name": r["student_name"], "student_user_id": r["student_user_id"],
            "check_in_time": "0:00" if r["status"] == "leave" else (r["check_in_time"][-8:] if r["check_in_time"] else "—"),
            "status": r["status"],
            "label": STATUS_LABELS.get(r["status"], r["status"]),
            "department": r["department"] or "—",
            "job_number": r["job_number"] or "—",
            "manual_note": r["manual_note"] or "",
        }
        for r in rows
    ]


# ── 页面路由 ──

@router.get("/")
async def dashboard(
    request: Request,
    view_slot: str = Query(""),
    view_dept: str = Query(""),
    view_date: str = Query(""),
    view_time: str = Query(""),
):
    config = load_config()
    class_names = [c["name"] for c in config.get("schedule", [])]
    dept_labels = config.get("dept_labels", {})
    dept_options = [(str(k), v) for k, v in dept_labels.items()]
    today_classes = _get_today_classes(config)
    checked_count = sum(1 for c in today_classes if c["checked"])
    pending_count = sum(1 for c in today_classes if c["pending"])

    target_date = view_date if view_date else date.today().strftime("%Y-%m-%d")
    today_str = target_date

    # 用时间匹配对应时段名用于筛选
    slot_filter = view_slot or _time_to_slot(view_time)
    dept_names = [_dept_id_to_name(d.strip()) for d in view_dept.split(",") if d.strip()] if view_dept else []

    with db_session() as conn:
        stats_sql = """SELECT COUNT(*) as total,
                      SUM(CASE WHEN status='on_time' THEN 1 ELSE 0 END) as on_time_cnt,
                      SUM(CASE WHEN status='leave_out' THEN 1 ELSE 0 END) as leave_out_cnt,
                      SUM(CASE WHEN status='leave_in' THEN 1 ELSE 0 END) as leave_in_cnt,
                      SUM(CASE WHEN status='absent' THEN 1 ELSE 0 END) as absent_cnt,
                      SUM(CASE WHEN status='makeup' THEN 1 ELSE 0 END) as makeup_cnt,
                      SUM(CASE WHEN manual_note != '' THEN 1 ELSE 0 END) as note_cnt
               FROM attendance_records WHERE class_date=?"""
        stats_params = [today_str]
        if dept_names:
            placeholders = ",".join("?" * len(dept_names))
            stats_sql += f" AND department IN ({placeholders})"
            stats_params.extend(dept_names)
        row = conn.execute(stats_sql, stats_params).fetchone()
        total = row["total"] if row else 0
        on_time_count = row["on_time_cnt"] if row else 0
        leave_out_count = row["leave_out_cnt"] if row else 0
        leave_in_count = row["leave_in_cnt"] if row else 0
        absent_count = row["absent_cnt"] if row else 0
        makeup_count = row["makeup_cnt"] if row else 0
        note_count = row["note_cnt"] if row else 0
        attendance_rate = round((on_time_count + leave_out_count + leave_in_count + makeup_count) / total * 100) if total > 0 else 100

        trend = []
        for i in range(6, -1, -1):
            d = date.today() - timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            r = conn.execute(
                """SELECT COUNT(*) as total,
                          SUM(CASE WHEN status!='absent' THEN 1 ELSE 0 END) as present
                   FROM attendance_records WHERE class_date=?""",
                (ds,)
            ).fetchone()
            t = r["total"] if r else 0
            p = r["present"] if r else 0
            trend.append({"date": ds[-5:], "rate": round(p / t * 100) if t > 0 else 0, "total": t})

        dist = conn.execute(
            """SELECT status, COUNT(*) as cnt FROM attendance_records WHERE class_date=? GROUP BY status""",
            (today_str,)
        ).fetchall()
        status_dist = {r["status"]: r["cnt"] for r in dist}

    recent = _query_records(class_name=slot_filter, departments=dept_names, date_from=target_date, date_to=target_date, limit=30)
    last_report = next((s["report"] for s in _job_status.values() if s.get("report")), None)

    return templates.TemplateResponse("index.html", {
        "request": request, "active_page": "dashboard",
        "today_classes": today_classes, "class_names": class_names,
        "dept_options": dept_options,
        "checked_count": checked_count, "pending_count": pending_count,
        "attendance_rate": attendance_rate,
        "total_count": total, "on_time_count": on_time_count,
        "leave_out_count": leave_out_count, "leave_in_count": leave_in_count, "absent_count": absent_count,
        "makeup_count": makeup_count, "note_count": note_count,
        "trend": trend, "status_dist": status_dist,
        "recent_records": recent, "last_report": last_report,
        "filters": {"view_slot": view_slot, "view_dept": view_dept, "view_date": view_date, "view_time": view_time},
    })


@router.get("/history")
async def history(
    request: Request,
    class_name: str = Query(""),
    date_from: str = Query(""),
    date_to: str = Query(""),
    status: str = Query(""),
    department: str = Query(""),
    view_time: str = Query(""),
):
    config = load_config()
    class_names = [c["name"] for c in config.get("schedule", [])]
    dept_labels = config.get("dept_labels", {})
    dept_options = [(str(k), v) for k, v in dept_labels.items()]
    dept_names = [_dept_id_to_name(d.strip()) for d in department.split(",") if d.strip()] if department else []
    slot_filter = class_name or _time_to_slot(view_time)
    records = _query_records(class_name=slot_filter, date_from=date_from,
                              date_to=date_to, status=status, departments=dept_names if dept_names else None)

    return templates.TemplateResponse("history.html", {
        "request": request, "active_page": "history",
        "records": records, "total_records": len(records),
        "class_names": class_names,
        "dept_options": dept_options,
        "filters": {"class_name": class_name, "date_from": date_from,
                     "date_to": date_to, "status": status,
                     "department": department, "view_time": view_time},
        "status_options": [
            ("", "全部状态"), ("absent", "❌ 缺卡"), ("leave_out", "🚶 外出请假"), ("leave_in", "🏫 在校请假"), ("makeup", "🔧 已补卡"), ("on_time", "✅ 出勤"),
        ],
    })


@router.get("/schedule")
async def schedule_page(request: Request):
    config = load_config()
    job_statuses = check_schedule_status()
    schedules = [
        {
            "name": s["name"],
            "weekday_label": ",".join(WEEKDAY_NAMES[d] for d in s.get("weekdays", [s.get("weekday", 0)])),
            "time": s["time"],
            "duration_minutes": s.get("duration_minutes", 180),
            "notify_after_minutes": s.get("notify_after_minutes", 5),
            "dept_id": s.get("dept_id", "N/A"),
        }
        for s in config.get("schedule", [])
    ]
    dept_labels = config.get("dept_labels", {})
    return templates.TemplateResponse("schedule.html", {
        "request": request, "active_page": "schedule",
        "job_statuses": job_statuses, "schedules": schedules,
        "dept_labels": dept_labels,
        "dept_options": [(str(k), v) for k, v in dept_labels.items()],
    })


@router.get("/students")
async def students_page(
    request: Request,
    stu_slot: str = Query(""),
    stu_dept: str = Query(""),
    stu_time: str = Query(""),
):
    """学生出勤统计，支持按时间段和部门筛选"""
    config = load_config()
    class_names = [c["name"] for c in config.get("schedule", [])]
    dept_labels = config.get("dept_labels", {})
    dept_options = [(str(k), v) for k, v in dept_labels.items()]

    sql = """SELECT student_name, student_user_id,
                    MAX(job_number) as job_number,
                    MAX(department) as dept,
                    COUNT(*) as total,
                    SUM(CASE WHEN status='on_time' THEN 1 ELSE 0 END) as on_time_cnt,
                    SUM(CASE WHEN status='absent' THEN 1 ELSE 0 END) as absent_cnt
             FROM attendance_records WHERE 1=1"""
    params = []

    slot_filter = stu_slot or _time_to_slot(stu_time)
    if slot_filter:
        sql += " AND class_name = ?"
        params.append(slot_filter)
    if stu_dept:
        sql += " AND department = ?"
        params.append(_dept_id_to_name(stu_dept))

    sql += """ GROUP BY student_user_id
               ORDER BY SUM(CASE WHEN status='absent' THEN 1 ELSE 0 END) DESC,
                        SUM(CASE WHEN status IN ('late','late_long') THEN 1 ELSE 0 END) DESC"""

    with db_session() as conn:
        rows = conn.execute(sql, params).fetchall()

    students = [
        {
            "name": r["student_name"], "user_id": r["student_user_id"],
            "job_number": r["job_number"] or "—",
            "dept": r["dept"] or "—",
            "total": r["total"], "on_time": r["on_time_cnt"],
            "absent": r["absent_cnt"],
            "rate": round(r["on_time_cnt"] / r["total"] * 100) if r["total"] else 0,
        }
        for r in rows
    ]

    return templates.TemplateResponse("students.html", {
        "request": request, "active_page": "students",
        "students": students, "total_students": len(students),
        "class_names": class_names, "dept_options": dept_options,
        "filters": {"stu_slot": stu_slot, "stu_dept": stu_dept, "stu_time": stu_time},
    })


# ── API ──

@router.get("/api/trigger-check")
async def api_trigger_check(
    class_name: str = Query(""),
    check_date: str = Query(""),
    check_time: str = Query(""),
    dept_ids: str = Query(""),
):
    config = load_config()
    template = config.get("schedule", [{}])[0]
    if class_name:
        t = next((c for c in config.get("schedule", []) if c["name"] == class_name), None)
        if t: template = t
    if check_time:
        slot_name = _time_to_slot(check_time) or f"手动考勤 {check_time}"
        template = {**template, "time": check_time, "name": slot_name}
    try:
        override_dept = [int(d.strip()) for d in dept_ids.split(",") if d.strip()] if dept_ids else None
        run_attendance_check(template, config, override_date=check_date, override_dept_ids=override_dept)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/api/export-csv")
async def api_export_csv(
    class_name: str = Query(""),
    date_from: str = Query(""),
    date_to: str = Query(""),
    department: str = Query(""),
    view_time: str = Query(""),
):
    slot_filter = class_name or _time_to_slot(view_time)
    dept_name = _dept_id_to_name(department)
    records = _query_records(class_name=slot_filter, date_from=date_from,
                              date_to=date_to, department=dept_name, limit=50000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["课程", "日期", "上课时间", "学生", "工号", "部门", "打卡时间", "状态", "备注"])
    for r in records:
        writer.writerow([r["class_name"], r["class_date"], r["class_start_time"],
                         r["student_name"], r.get("job_number",""), r.get("department",""),
                         r["check_in_time"], r["label"], r.get("manual_note","")])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename=attendance_{date.today()}.csv"}
    )


@router.post("/api/set-note")
async def api_set_note(
    class_name: str = Query(...),
    student_user_id: str = Query(...),
    check_date: str = Query(...),
    note: str = Query(""),
    makeup_time: str = Query(""),
):
    """手动设置缺卡学生的备注和补卡时间"""
    with db_session() as conn:
        if makeup_time:
            # 补卡：更新打卡时间和状态为已补卡
            full_time = f"{check_date} {makeup_time}:00"
            conn.execute(
                "UPDATE attendance_records SET manual_note=?, check_in_time=?, status='makeup' WHERE class_name=? AND class_date=? AND student_user_id=?",
                (note or "补卡", full_time, class_name, check_date, student_user_id)
            )
            return {"ok": True, "action": "补卡已记录"}
        else:
            conn.execute(
                "UPDATE attendance_records SET manual_note=? WHERE class_name=? AND class_date=? AND student_user_id=?",
                (note, class_name, check_date, student_user_id)
            )
            return {"ok": True}


@router.post("/api/reset-data")
async def api_reset_data():
    """清空所有考勤记录和通知日志"""
    with db_session() as conn:
        conn.execute("DELETE FROM attendance_records")
        conn.execute("DELETE FROM notify_logs")
    return {"ok": True, "message": "所有数据已清空"}


@router.post("/api/mark-leave")
async def api_mark_leave(
    class_name: str = Query(...),
    student_user_id: str = Query(...),
    check_date: str = Query(""),
):
    """手动标记/取消请假"""
    target_date = check_date if check_date else date.today().strftime("%Y-%m-%d")
    with db_session() as conn:
        row = conn.execute(
            """SELECT id, status, student_name, job_number, department
               FROM attendance_records
               WHERE class_name=? AND class_date=? AND student_user_id=?""",
            (class_name, target_date, student_user_id)
        ).fetchone()
        if row:
            # 切换：已是请假→恢复缺勤，否则→请假
            new_status = 'absent' if row["status"] == 'leave' else 'leave'
            conn.execute("UPDATE attendance_records SET status=? WHERE id=?", (new_status, row["id"]))
            return {"ok": True, "action": "toggled", "new_status": new_status}
        else:
            # 无记录，查姓名和工号
            name = student_user_id
            job_number = ""
            dept = ""
            ref = conn.execute(
                "SELECT student_name, job_number, department FROM attendance_records WHERE student_user_id=? LIMIT 1",
                (student_user_id,)
            ).fetchone()
            if ref:
                name = ref["student_name"]
                job_number = ref["job_number"] or ""
                dept = ref["department"] or ""
            config = load_config()
            cls = next((c for c in config["schedule"] if c["name"] == class_name), None)
            time_str = cls["time"] if cls else "00:00"
            conn.execute(
                """INSERT INTO attendance_records
                   (class_name, class_date, class_start_time,
                    student_name, student_user_id, check_in_time,
                    status, job_number, department)
                   VALUES (?, ?, ?, ?, ?, NULL, 'leave', ?, ?)""",
                (class_name, target_date, time_str, name, student_user_id, job_number, dept)
            )
            return {"ok": True, "action": "created"}
