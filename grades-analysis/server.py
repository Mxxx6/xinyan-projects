#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
画室成绩分析系统 — 无 Django 单文件版

仅用 Python 标准库（http.server + sqlite3），一条命令启动：
    python3 server.py [端口]

默认端口 8081，同一个服务同时提供：
  - 前端静态页（static/index.html、app.js）
  - JSON 接口（/api/...）

数据实时来自简道云 API（内存缓存数分钟），Excel 导入的数据存在本地 data.db 并合并展示。
"""
import io
import json
import re
import os
import sys
import time
import sqlite3
import datetime
import threading
import zipfile
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATA_DB", os.path.join(HERE, "data.db"))
STATIC_DIR = os.path.join(HERE, "static")

# ── 简道云 API 配置 ─────────────────────────────────
JDY_BASE_URL = "https://api.jiandaoyun.com/api/v2"
JDY_APP_ID = os.environ.get("JDY_APP_ID", "")
JDY_API_KEY = os.environ.get("JDY_API_KEY", "")
JDY_ARCHIVE_ENTRY_ID = os.environ.get("JDY_ARCHIVE_ENTRY_ID", "")
JDY_EXAM_ENTRY_ID = os.environ.get("JDY_EXAM_ENTRY_ID", "")

# 9分制档位（顺序即权重）
GRADES = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D"]
GRADE_POINT = {"A+": 9, "A": 8, "A-": 7, "B+": 6, "B": 5,
               "B-": 4, "C+": 3, "C": 2, "C-": 1, "D": 0}
DIRECT_GRADE = {9: "A+", 8: "A", 7: "A-", 6: "B+", 5: "B",
                4: "B-", 3: "C+", 2: "C", 1: "C-", 0: "D"}
# 100分制原始分 → 档位（与前端 gradeBand / 原 ScoreRangeConfig 一致）
RAW_RANGES = [(95, "A+"), (90, "A"), (85, "A-"), (80, "B+"), (75, "B"),
              (70, "B-"), (65, "C+"), (60, "C"), (50, "C-"), (0, "D")]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def classify(score):
    """判定档位：≤9 直接映射 9分制，>9 按原始分阈值"""
    if score is None:
        return None
    if 0 <= score <= 9:
        return DIRECT_GRADE.get(int(round(score)), "D")
    for lo, g in RAW_RANGES:
        if score >= lo:
            return g
    return "D"


def _split(v):
    return [x for x in (v or "").split(",") if x]


# ═══════════════════════════════════════════════════
#  数据层：实时拉取简道云（内存缓存）+ 合并本地 Excel 数据
# ═══════════════════════════════════════════════════

_jdy_lock = threading.Lock()   # 保护同步写入，避免并发同步


def _init_db():
    """建简道云缓存表（幂等）"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jdy_student (
            _id TEXT PRIMARY KEY,
            student_code TEXT, name TEXT, province TEXT, group_tag TEXT,
            studio_name TEXT, class_name TEXT, term TEXT
        );
        CREATE TABLE IF NOT EXISTS jdy_score (
            _id TEXT PRIMARY KEY,
            student_code TEXT, exam_type TEXT, exam_month TEXT, exam_session TEXT,
            sketch_score REAL, color_score REAL, quick_score REAL, total_score REAL
        );
        CREATE TABLE IF NOT EXISTS jdy_sync (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_success_at TEXT, status TEXT, message TEXT,
            student_count INTEGER, score_count INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_jdy_student_code ON jdy_student(student_code);
        CREATE INDEX IF NOT EXISTS idx_jdy_score_student ON jdy_score(student_code);
        CREATE INDEX IF NOT EXISTS idx_jdy_score_key ON jdy_score(exam_type, exam_month, exam_session);
    """)
    conn.commit()
    conn.close()


def _normalize_student(it):
    """简道云档案记录 → 学生 dict（含 _id），学号/姓名缺失返回 None"""
    xh = str(it.get("userid2", "")).strip()
    name = str(it.get("username", "")).strip()
    if not xh or not name:
        return None
    return {
        "_id": it.get("_id"),
        "student_code": xh, "name": name,
        "province": str(it.get("address", "")).strip(),
        "group_tag": str(it.get("hezuo", "")).strip(),
        "studio_name": str(it.get("gongzuoshi", "")).strip(),
        "class_name": str(it.get("userszbj", "")).strip(),
        "term": str(it.get("xuejie", "")).strip(),
    }


def _normalize_scores(raw_list):
    """简道云成绩原始记录 → 成绩 dict 列表（含 _id），按场次分月考/联考"""
    raw = []
    for it in raw_list:
        sc = str(it.get("_widget_1564553107561", "")).strip()
        em, sess = _parse_exam_date(it.get("_widget_1566305212408", ""))
        if not sc or not em:
            continue
        raw.append({
            "_id": it.get("_id"),
            "student_code": sc, "exam_month": em, "exam_session": sess,
            "sketch": _to_float(it.get("_widget_1564553107692")),
            "color": _to_float(it.get("_widget_1564553107677")),
            "quick": _to_float(it.get("_widget_1564553107707")),
            "total": _to_float(it.get("_widget_1564553107722")),
            "text": {"sketch": it.get("_widget_1628064062394"),
                     "color": it.get("_widget_1628064062412"),
                     "quick": it.get("_widget_1628064062376")},
            "named": not re.match(r"^\d{4}-\d{2}$", em),
        })

    # 按场次判定联考——命名场次(XX模考/一模…)必联考；日期场次任一记录 >9 分即联考
    joint_keys = set()
    for r in raw:
        if r["named"] or _is_joint(r["sketch"], r["color"], r["quick"], r["total"]):
            joint_keys.add((r["exam_month"], r["exam_session"]))

    out = []
    for r in raw:
        exam_type = "joint" if (r["exam_month"], r["exam_session"]) in joint_keys else "monthly"
        sketch, color, quick, total = r["sketch"], r["color"], r["quick"], r["total"]
        tx = r["text"]
        # 文本字段：月考存字母档位(A+/B…)，联考存原始分数字字符串(如 "88")
        if sketch is None:
            sketch = (LETTER_TO_SCORE.get(str(tx["sketch"]).strip())
                      if exam_type == "monthly" else _to_float(tx["sketch"]))
        if color is None:
            color = (LETTER_TO_SCORE.get(str(tx["color"]).strip())
                     if exam_type == "monthly" else _to_float(tx["color"]))
        if quick is None:
            quick = (LETTER_TO_SCORE.get(str(tx["quick"]).strip())
                     if exam_type == "monthly" else _to_float(tx["quick"]))
        if total is None:
            total = (sketch or 0) + (color or 0) + (quick or 0)
        out.append({"_id": r["_id"], "student_code": r["student_code"],
                    "exam_type": exam_type, "exam_month": r["exam_month"],
                    "exam_session": r["exam_session"], "sketch_score": sketch,
                    "color_score": color, "quick_score": quick, "total_score": total})
    return out


def sync_jdy():
    """全量拉取简道云并落地 SQLite。拉取完整才替换旧数据，否则保留旧数据兜底。"""
    with _jdy_lock:
        term = _current_term_code()
        s_filters = ([{"field": "xuejie", "type": "text", "method": "eq", "value": [term]}]
                     if term else None)
        x_filters = ([{"field": "_widget_1656764693061", "type": "text", "method": "eq", "value": [term]}]
                     if term else None)
        t0 = time.time()
        raw_students, ok1 = _jdy_fetch(JDY_ARCHIVE_ENTRY_ID, s_filters)
        raw_scores, ok2 = _jdy_fetch(JDY_EXAM_ENTRY_ID, x_filters)
        complete = ok1 and ok2
        students = [s for s in (_normalize_student(it) for it in raw_students) if s]
        scores = _normalize_scores(raw_scores)
        cost = round(time.time() - t0, 1)

        conn = get_db()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        if complete:
            # 全量替换：先清空再批量写入（同一事务，失败回滚不丢旧数据）
            conn.execute("DELETE FROM jdy_student")
            conn.execute("DELETE FROM jdy_score")
            conn.executemany(
                "INSERT INTO jdy_student (_id, student_code, name, province, group_tag, "
                "studio_name, class_name, term) VALUES (?,?,?,?,?,?,?,?)",
                [(s["_id"], s["student_code"], s["name"], s["province"], s["group_tag"],
                  s["studio_name"], s["class_name"], s["term"]) for s in students])
            conn.executemany(
                "INSERT INTO jdy_score (_id, student_code, exam_type, exam_month, exam_session, "
                "sketch_score, color_score, quick_score, total_score) VALUES (?,?,?,?,?,?,?,?,?)",
                [(s["_id"], s["student_code"], s["exam_type"], s["exam_month"], s["exam_session"],
                  s["sketch_score"], s["color_score"], s["quick_score"], s["total_score"])
                 for s in scores])
            conn.execute(
                "INSERT INTO jdy_sync (id, last_success_at, status, message, student_count, score_count) "
                "VALUES (1, ?, 'ok', '', ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET last_success_at=excluded.last_success_at, "
                "status='ok', message='', student_count=excluded.student_count, "
                "score_count=excluded.score_count",
                (now, len(students), len(scores)))
            conn.commit()
            msg = "同步完成：学生 %d，成绩 %d，耗时 %.1fs" % (len(students), len(scores), cost)
        else:
            # 拉取不完整：保留旧数据，只更新状态标记
            conn.execute(
                "INSERT INTO jdy_sync (id, last_success_at, status, message, student_count, score_count) "
                "VALUES (1, ?, 'incomplete', ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status='incomplete', message=excluded.message",
                (now, "拉取不完整，已保留上次完整数据", len(students), len(scores)))
            conn.commit()
            msg = "同步不完整（保留旧数据兜底）：本次拉到学生 %d / 成绩 %d，耗时 %.1fs" % (
                len(students), len(scores), cost)
        conn.close()
        print(msg, flush=True)
        return {"ok": complete, "message": msg, "student_count": len(students),
                "score_count": len(scores), "cost": cost}


def _jdy_all_students():
    """读取简道云学生快照（SQLite）"""
    rows = get_db().execute(
        "SELECT student_code, name, province, group_tag, studio_name, class_name, term "
        "FROM jdy_student").fetchall()
    return [dict(r) for r in rows]


def _jdy_all_scores():
    """读取简道云成绩快照（SQLite）"""
    rows = get_db().execute(
        "SELECT student_code, exam_type, exam_month, exam_session, "
        "sketch_score, color_score, quick_score, total_score FROM jdy_score").fetchall()
    return [dict(r) for r in rows]


def get_live_data(force=False):
    """读取简道云本地快照（SQLite 持久缓存）；force 仅作兼容保留"""
    return _jdy_all_students(), _jdy_all_scores()


def api_sync_status(p=None):
    """同步状态（供前端展示最后同步时间/结果）；syncing 表示后台正在同步"""
    conn = get_db()
    row = conn.execute(
        "SELECT last_success_at, status, message, student_count, score_count "
        "FROM jdy_sync WHERE id = 1").fetchone()
    conn.close()
    syncing = _jdy_lock.locked()
    if not row:
        return {"synced": False, "last_success_at": None, "status": "never",
                "message": "尚未同步", "student_count": 0, "score_count": 0,
                "syncing": syncing}
    return {"synced": row["status"] == "ok", "last_success_at": row["last_success_at"],
            "status": row["status"], "message": row["message"],
            "student_count": row["student_count"], "score_count": row["score_count"],
            "syncing": syncing}


def _local_students():
    # 仅取当前学届的本地 Excel 数据，避免换届后旧届数据混入当前届分析
    term = _current_term_code()
    sql = ("SELECT s.student_code, s.name, s.province, s.group_tag, s.enrolled_term, "
           "st.name AS studio_name, c.name AS class_name "
           "FROM student s LEFT JOIN studio st ON s.studio_id = st.id "
           "LEFT JOIN \"class\" c ON s._class_id = c.id "
           "WHERE s.status = 'active'")
    args = ()
    if term:
        sql += " AND s.enrolled_term = ?"
        args = (term,)
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


def _local_scores():
    # 同上：只保留当前学届的本地成绩
    term = _current_term_code()
    sql = ("SELECT s.student_code, e.exam_type, e.exam_month, e.exam_session, "
           "e.sketch_score, e.color_score, e.quick_score, e.total_score "
           "FROM exam_score e JOIN student s ON e.student_id = s.id "
           "WHERE s.status = 'active'")
    args = ()
    if term:
        sql += " AND s.enrolled_term = ?"
        args = (term,)
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


def merged_data():
    """简道云实时数据 + 本地库（仅 Excel 导入），按学号/成绩键去重，简道云优先"""
    students, scores = get_live_data()
    live_codes = {s["student_code"] for s in students}
    live_keys = {(s["student_code"], s["exam_type"], s["exam_month"], s["exam_session"])
                 for s in scores}
    for st in _local_students():
        if st["student_code"] and st["student_code"] not in live_codes:
            students.append({"student_code": st["student_code"], "name": st["name"],
                             "province": st["province"] or "", "group_tag": st["group_tag"] or "",
                             "studio_name": st["studio_name"], "class_name": st["class_name"],
                             "term": st["enrolled_term"] or ""})
    for sc in _local_scores():
        key = (sc["student_code"], sc["exam_type"], sc["exam_month"], sc["exam_session"])
        if sc["student_code"] and key not in live_keys:
            scores.append({"student_code": sc["student_code"], "exam_type": sc["exam_type"],
                           "exam_month": sc["exam_month"], "exam_session": sc["exam_session"],
                           "sketch_score": sc["sketch_score"], "color_score": sc["color_score"],
                           "quick_score": sc["quick_score"], "total_score": sc["total_score"]})
    return students, scores


def _build_rows(p):
    """合并数据 + 按查询参数过滤，返回带学生信息的成绩行列表"""
    students, scores = merged_data()
    stu = {s["student_code"]: s for s in students}
    et = p.get("exam_type", "monthly")
    em = p.get("exam_month")
    es = p.get("exam_session")
    prov = p.get("province")
    studios = _split(p.get("studios"))
    classes = _split(p.get("classes"))
    name = p.get("student_name")
    rows = []
    for sc in scores:
        if sc["exam_type"] != et:
            continue
        if em and sc["exam_month"] != em:
            continue
        if es and sc["exam_session"] != es:
            continue
        s = stu.get(sc["student_code"])
        if not s:
            continue
        sp = s["province"] or ""
        if prov == "非浙江省":
            if sp == "浙江省":
                continue
        elif prov:
            if sp != prov:
                continue
        if studios and s["studio_name"] not in studios:
            continue
        if classes and s["class_name"] not in classes:
            continue
        if name and name not in (s["name"] or ""):
            continue
        rows.append({
            "student_name": s["name"], "student_code": sc["student_code"],
            "province": sp, "studio_name": s["studio_name"] or "",
            "class_name": s["class_name"] or "",
            "sketch_score": sc["sketch_score"], "color_score": sc["color_score"],
            "quick_score": sc["quick_score"], "total_score": sc["total_score"],
        })
    return rows


def api_sessions(p):
    _, scores = merged_data()
    et = p.get("exam_type", "monthly")
    seen = {}  # key -> 去重学生集合，用于统计每场成绩人数
    result = []
    for sc in scores:
        if sc["exam_type"] != et or not sc["exam_month"]:
            continue
        key = (sc["exam_month"], sc["exam_session"])
        seen.setdefault(key, set()).add(sc["student_code"])
    for (em, sess), codes in seen.items():
        session = sess or ""
        dm = re.search(r"(\d{1,2})月(\d{1,2})日", session)
        day = dm.group(2) if dm else "01"
        y, m = em[:4], em[5:7]
        result.append({"exam_month": em, "exam_session": session,
                       "date": "%s-%s-%02d" % (y, m, int(day)),
                       "count": len(codes)})
    result.sort(key=lambda x: (x["exam_month"], x["exam_session"]))
    return result


def api_provinces(p):
    students, scores = merged_data()
    et = p.get("exam_type", "joint")
    stu = {s["student_code"]: s for s in students}
    provs = set()
    for sc in scores:
        if sc["exam_type"] != et:
            continue
        s = stu.get(sc["student_code"])
        if s and s["province"]:
            provs.add(s["province"])
    return sorted(provs)


def api_ranking(p):
    rows = sorted(_build_rows(p), key=lambda r: -(r["total_score"] or 0))
    result = []
    current_rank, prev_total, skip = 0, None, 0
    for r in rows:
        total = r["total_score"] or 0
        if total != prev_total:
            current_rank = current_rank + 1 + skip
            skip = 0
        else:
            skip += 1
        prev_total = total
        result.append({
            "student_name": r["student_name"], "student_code": r["student_code"],
            "province": r["province"], "studio_name": r["studio_name"],
            "class_name": r["class_name"],
            "sketch_score": r["sketch_score"], "color_score": r["color_score"],
            "quick_score": r["quick_score"], "total_score": r["total_score"],
            "rank": current_rank,
        })
    return result


def api_averages(p):
    rows = _build_rows(p)

    group_by = p.get("group_by", "studio")
    groups = {}
    for r in rows:
        if group_by == "class":
            key = r["class_name"] or "未知"
        elif group_by == "province":
            key = r["province"] or "未知"
        else:
            key = r["studio_name"] or "未知"
        g = groups.setdefault(key, {"sketch": [], "color": [], "quick": []})
        if r["sketch_score"] is not None:
            g["sketch"].append(r["sketch_score"])
        if r["color_score"] is not None:
            g["color"].append(r["color_score"])
        if r["quick_score"] is not None:
            g["quick"].append(r["quick_score"])

    result = []
    for key, g in groups.items():
        avg_s = sum(g["sketch"]) / len(g["sketch"]) if g["sketch"] else 0
        avg_c = sum(g["color"]) / len(g["color"]) if g["color"] else 0
        avg_q = sum(g["quick"]) / len(g["quick"]) if g["quick"] else 0
        result.append({
            "label": key, "student_count": len(g["sketch"]),
            "avg_sketch": round(avg_s, 1), "avg_color": round(avg_c, 1),
            "avg_quick": round(avg_q, 1),
            "avg_total": round((avg_s + avg_c + avg_q) / 3, 1),
        })
    result.sort(key=lambda x: x["avg_total"], reverse=True)
    return result


def _score_bands(p):
    rows = _build_rows(p)
    subjects = ["sketch", "color", "quick"]
    studio_data = {}
    for r in rows:
        sn = r["studio_name"] or "未知"
        if sn not in studio_data:
            studio_data[sn] = {"total": 0,
                               "bands": {s: {g: 0 for g in GRADES} for s in subjects}}
        studio_data[sn]["total"] += 1
        for subj in subjects:
            band = classify(r[subj + "_score"])
            if band:
                studio_data[sn]["bands"][subj][band] += 1

    results = []
    for sn, data in studio_data.items():
        total = data["total"] or 1
        for subj in subjects:
            for grade in GRADES:
                count = data["bands"][subj][grade]
                results.append({
                    "studio": sn, "subject": subj, "grade": grade,
                    "grade_point": GRADE_POINT[grade], "count": count,
                    "studio_ratio": round(count / total * 100, 1),
                })
    return results


def api_score_distribution(p):
    data = _score_bands(p)
    subject = p.get("subject", "")
    if subject:
        subj = subject.replace("_score", "")
        data = [d for d in data if d["subject"] == subj]
    return data


def api_teaching_index(p):
    bands = _score_bands(p)
    studio_data = {}
    for item in bands:
        sn = item["studio"]
        d = studio_data.setdefault(sn, {"weighted": 0, "total": 0})
        d["weighted"] += item["count"] * item["grade_point"]
        d["total"] += item["count"]
    result = []
    for sn, d in studio_data.items():
        idx = round(d["weighted"] / d["total"], 2) if d["total"] else 0
        result.append({"studio": sn, "teaching_index": idx})
    result.sort(key=lambda x: x["teaching_index"], reverse=True)
    return result


def api_studios(p=None):
    students, _ = merged_data()
    names = sorted({s["studio_name"] for s in students if s["studio_name"]})
    return {"results": [{"name": n} for n in names]}


def api_classes(p=None):
    students, _ = merged_data()
    names = sorted({s["class_name"] for s in students if s["class_name"]})
    return {"results": [{"name": n} for n in names]}


def api_students(p=None):
    students, _ = merged_data()
    out = [{"student_code": s["student_code"], "name": s["name"],
            "province": s["province"] or "", "group_tag": s["group_tag"] or "",
            "enrolled_term": s["term"] or "", "status": "active"} for s in students]
    out.sort(key=lambda x: x["student_code"])
    return {"results": out}


def api_groups(p=None):
    """团体生统计：按 group_tag 分组，按考试类型+场次计算均分（人数≥5）。
    exam_month='__all__' 时聚合该类型全部场次（团体生成绩分散在多场次，单场永远不全）。"""
    exam_type = (p or {}).get("exam_type") or "monthly"
    if exam_type not in ("monthly", "joint"):
        exam_type = "monthly"
    em = (p or {}).get("exam_month") or ""
    es = (p or {}).get("exam_session") or ""
    students, scores = merged_data()
    # 该类型全部场次；未指定场次时默认选成绩人数最多的一场（覆盖面最广），而非字母序最后一场
    sessions = sorted({(s["exam_month"], s["exam_session"]) for s in scores
                       if s["exam_type"] == exam_type and s["exam_month"]})
    if not sessions:
        return {"results": []}
    all_mode = (em == "__all__")
    if not em:
        cnt = {}
        for s in scores:
            if s["exam_type"] == exam_type and s["exam_month"]:
                k = (s["exam_month"], s["exam_session"])
                cnt[k] = cnt.get(k, 0) + 1
        em, es = max(cnt, key=cnt.get)
    # 收集每个学生在本类型下的成绩（all_mode 下同一学生可能有多条不同场次）
    score_by_code = {}
    for s in scores:
        if s["exam_type"] != exam_type:
            continue
        if all_mode or (s["exam_month"] == em and s["exam_session"] == es):
            score_by_code.setdefault(s["student_code"], []).append(s)

    groups = {}
    for st in students:
        tag = (st.get("group_tag") or "").strip()
        if not tag:
            continue
        g = groups.setdefault(tag, {"count": 0, "sketch": [], "color": [], "quick": []})
        g["count"] += 1
        for sc in score_by_code.get(st["student_code"], []):
            if sc["sketch_score"] is not None:
                g["sketch"].append(sc["sketch_score"])
            if sc["color_score"] is not None:
                g["color"].append(sc["color_score"])
            if sc["quick_score"] is not None:
                g["quick"].append(sc["quick_score"])

    def avg(a):
        return round(sum(a) / len(a), 1) if a else None

    out = []
    for tag, g in groups.items():
        if g["count"] < 5:
            continue
        sk, co, qu = avg(g["sketch"]), avg(g["color"]), avg(g["quick"])
        total = round((sk + co + qu) / 3, 1) if None not in (sk, co, qu) else None
        out.append({"name": tag, "count": g["count"],
                    "avg_sketch": sk, "avg_color": co, "avg_quick": qu,
                    "avg_total": total})
    out.sort(key=lambda x: -x["count"])
    return {"results": out}


# ═══════════════════════════════════════════════════
#  简道云数据同步（移植自原 apps/jiandaoyun/sync.py）
# ═══════════════════════════════════════════════════

def _jdy_fetch(entry_id, filters=None):
    """分页拉取简道云表单数据（stdlib urllib），带超时与重试。

    返回 (items, complete)：complete=False 表示中途失败、数据可能不完整。
    """
    PAGE = 200  # 单页条数；过大(如1000)响应~1MB会被简道云中途断连(IncompleteRead)
    url = "%s/app/%s/entry/%s/data" % (JDY_BASE_URL, JDY_APP_ID, entry_id)
    headers = {"Authorization": "Bearer %s" % JDY_API_KEY,
               "Content-Type": "application/json"}
    items = []
    skip = 0
    complete = True
    while True:
        body = {"limit": PAGE, "skip": skip}
        if filters:
            body["filter"] = {"rel": "and", "cond": filters}
        data = None
        for attempt in range(8):
            req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                         headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                break
            except Exception as e:
                print("简道云请求异常(第%d次): %s" % (attempt + 1, e), flush=True)
                # 指数退避，给简道云更长的恢复时间（2,4,8,16,30,30,30,30 秒）
                time.sleep(min(2 ** (attempt + 1), 30))
        if data is None:
            # 重试后仍失败，停止分页并标记不完整（返回已拉到的部分，避免死循环）
            print("简道云拉取失败，已停止于 skip=%d，累计 %d 条" % (skip, len(items)), flush=True)
            complete = False
            break
        batch = data.get("data", [])
        if not batch:
            break
        items.extend(batch)
        if len(batch) < PAGE:
            # 最后一页（不足一页），说明已拉全
            break
        skip += len(batch)
    return items, complete


def _current_term_code():
    row = get_db().execute(
        "SELECT name FROM term WHERE is_current = 1 ORDER BY id DESC LIMIT 1").fetchone()
    if row:
        return (row["name"] or "").replace("届", "")
    return ""


def _parse_exam_date(raw):
    """简道云月份字段 → (YYYY-MM, 场次名)"""
    raw = str(raw).strip()
    if re.match(r'\d{4}-\d{2}', raw):
        return raw, ""
    m = re.search(r'(\d{1,2})月\s*(\d{1,2})日', raw)
    if m:
        month = int(m.group(1))
        day = int(m.group(2))
        year = datetime.date.today().year
        return "%d-%02d" % (year, month), "%d月%d日" % (month, day)
    m = re.search(r'(\d{1,2})月', raw)
    if m:
        month = int(m.group(1))
        year = datetime.date.today().year
        return "%d-%02d" % (year, month), ""
    return raw, ""


def _to_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _is_joint(sketch, color, quick, total):
    """按分值制判定：月考 9 分制(总分≤27)，联考 100 分制(总分>27)"""
    if total is not None and total > 27:
        return True
    for s in (sketch, color, quick):
        if s is not None and s > 9:
            return True
    return False


LETTER_TO_SCORE = {"A+": 9, "A": 8, "A-": 7, "B+": 6, "B": 5,
                   "B-": 4, "C+": 3, "C": 2, "C-": 1, "D": 0}


def refresh_cache():
    """手动触发全量同步简道云（后台执行，前端轮询 /api/jdy/status/ 获取结果）"""
    threading.Thread(target=sync_jdy, daemon=True).start()
    return {"ok": True, "async": True, "message": "已在后台开始同步"}


def transition_migrate(body):
    """换届：切换当前学届。数据实时来自简道云，无需本地归档，只改当前届次并刷新缓存"""
    new_term = (body.get("new_term") or "").strip()
    confirm = (body.get("confirm") or "").strip()
    if confirm != "确认换届":
        return {"ok": False, "error": "请输入'确认换届'以确认操作"}
    if not new_term:
        return {"ok": False, "error": "请提供新届名称"}
    if not new_term.endswith("届"):
        new_term += "届"

    prev = _current_term_code() or ""
    conn = get_db()
    conn.execute("UPDATE term SET is_current = 0 WHERE is_current = 1")
    row = conn.execute("SELECT id FROM term WHERE name = ?", (new_term,)).fetchone()
    today = datetime.date.today().isoformat()
    if row:
        conn.execute("UPDATE term SET is_current = 1, start_date = ? WHERE id = ?",
                     (today, row[0]))
    else:
        conn.execute("INSERT INTO term (name, start_date, is_current) VALUES (?, ?, 1)",
                     (new_term, today))
    conn.commit()
    conn.close()

    # 后台异步同步新届数据（换届接口立即返回，避免大数据量拉取长时间阻塞）
    threading.Thread(target=sync_jdy, daemon=True).start()
    return {"ok": True, "async": True, "report": {"prev_term": prev, "new_term": new_term}}


# ═══════════════════════════════════════════════════
#  Excel 导入（写入本地 data.db，与简道云数据合并展示）
# ═══════════════════════════════════════════════════

# 列名 → 字段（与 Django 版 col_map 一致，做模糊匹配）
EXCEL_COL_MAP = {
    "学生姓名": "name", "学号": "student_code", "素描成绩": "sketch_score",
    "色彩成绩": "color_score", "速写成绩": "quick_score",
    "考试月份": "exam_month", "考试类型": "exam_type",
    "联考场次": "exam_session", "缺考标记": "is_absent",
}


def _match_col(headers, keyword):
    """按关键字模糊匹配表头，返回列索引（未命中返回 None）"""
    for i, h in enumerate(headers):
        h = str(h).strip()
        if not h:
            continue
        if keyword in h or h in keyword:
            return i
    return None


def _xlsx_cell_value(cell, shared):
    """解析 xlsx 单元格 → 字符串（t 为 s 时查共享字符串表）"""
    t = cell.get("t", "")
    v = None
    isnode = None
    for child in cell:
        if child.tag.endswith("}v"):
            v = child
        elif child.tag.endswith("}is"):
            isnode = child
    text = (v.text or "") if v is not None else ""
    if t == "s" and text:
        try:
            text = shared[int(text)]
        except (ValueError, IndexError):
            pass
    elif t == "inlineStr":
        text = "".join(node.text or "" for node in isnode.iter()) if isnode is not None else ""
    return text


def read_xlsx(data_bytes):
    """解析 .xlsx → (表头列表, 数据行列表[list of dict-by-header])，仅取第一个工作表"""
    zf = zipfile.ZipFile(io.BytesIO(data_bytes))
    shared = []
    if "xl/sharedStrings.xml" in zf.namelist():
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        for si in root.findall("m:si", ns):
            shared.append("".join(t.text or "" for t in si.iter() if t.tag.endswith("}t")))
    sheet = zf.read("xl/worksheets/sheet1.xml")
    root = ET.fromstring(sheet)
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows = []
    for row in root.findall(".//m:row", ns):
        cells = {}
        for c in row.findall("m:c", ns):
            ref = c.get("r") or ""
            m = re.match(r"([A-Z]+)(\d+)", ref)
            if not m:
                continue
            col = 0
            for ch in m.group(1):
                col = col * 26 + (ord(ch) - 64)
            cells[col - 1] = _xlsx_cell_value(c, shared)
        if cells:
            rows.append(cells)
    zf.close()
    if not rows:
        return [], []
    max_col = max(max(r) for r in rows)
    header = rows[0]
    headers = [header.get(i, "") for i in range(max_col + 1)]
    data = []
    for r in rows[1:]:
        data.append({h: r.get(i, "") for i, h in enumerate(headers) if h})
    return headers, data


def excel_import(data_bytes):
    """解析并导入 Excel 成绩，写入本地 data.db（返回 created/errors 统计）"""
    _, data = read_xlsx(data_bytes)
    if not data:
        return {"created": 0, "updated": 0, "errors": ["未读取到数据行"]}

    # 用第一行确定各字段列
    sample = data[0]
    col_idx = {}
    for keyword, field in EXCEL_COL_MAP.items():
        for h in sample:
            if keyword in str(h) or str(h) in keyword:
                col_idx[field] = h
                break

    conn = get_db()
    now = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
    created = updated = errors = 0
    err_list = []
    for row in data:
        try:
            def get(field):
                h = col_idx.get(field)
                return (row.get(h) or "").strip() if h else ""

            name = get("name")
            code = get("student_code")
            if not code and not name:
                continue
            sketch = _to_float(get("sketch_score"))
            color = _to_float(get("color_score"))
            quick = _to_float(get("quick_score"))
            total = (sketch or 0) + (color or 0) + (quick or 0)
            is_absent = 1 if get("is_absent") in ("是", "缺考", "1", "true", "True") else 0

            exam_type = get("exam_type") or ("joint" if _is_joint(sketch, color, quick, total) else "monthly")
            exam_month_raw = get("exam_month")
            exam_month, session = _parse_exam_date(exam_month_raw) if exam_month_raw else ("", "")
            if not exam_month:
                exam_month = datetime.date.today().strftime("%Y-%m")
            session = session or get("exam_session")

            # 定位学生：先查本地库，再查简道云实时（命中则落地一个最小本地学生）
            row_s = conn.execute("SELECT id FROM student WHERE student_code = ?",
                                 (code,)).fetchone()
            student_id = row_s[0] if row_s else None
            if not student_id:
                students, _ = get_live_data()
                match = next((s for s in students if s["student_code"] == code), None)
                if match:
                    conn.execute("INSERT INTO student (student_code, name, province, group_tag, "
                                 "enrolled_term, graduated_term, status, created_at) "
                                 "VALUES (?, ?, ?, ?, ?, '', 'active', ?)",
                                 (code, match["name"], match["province"], match["group_tag"],
                                  match["term"], now))
                    student_id = conn.execute(
                        "SELECT id FROM student WHERE student_code = ?", (code,)).fetchone()[0]
            if not student_id:
                # 学生不存在，尝试按姓名兜底
                row_s = conn.execute("SELECT id FROM student WHERE name = ?", (name,)).fetchone()
                student_id = row_s[0] if row_s else None
            if not student_id:
                err_list.append("学生不存在: %s %s" % (code, name))
                errors += 1
                continue

            exists = conn.execute(
                "SELECT id FROM exam_score WHERE student_id = ? AND exam_type = ? "
                "AND exam_month = ? AND exam_session = ?",
                (student_id, exam_type, exam_month, session)).fetchone()
            if exists:
                conn.execute("UPDATE exam_score SET sketch_score = ?, color_score = ?, "
                             "quick_score = ?, total_score = ?, is_absent = ? WHERE id = ?",
                             (sketch, color, quick, total, is_absent, exists[0]))
                updated += 1
            else:
                conn.execute("INSERT INTO exam_score (exam_type, exam_month, exam_session, "
                             "sketch_score, color_score, quick_score, total_score, "
                             "is_absent, created_at, student_id) "
                             "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (exam_type, exam_month, session, sketch, color, quick,
                              total, is_absent, now, student_id))
                created += 1
        except Exception as e:
            print("Excel 导入行失败:", e)
            errors += 1
    conn.commit()
    conn.close()
    print("Excel 导入完成: 新增 %d, 更新 %d, 错误 %d" % (created, updated, errors))
    return {"created": created, "updated": updated, "errors": err_list}


# ═══════════════════════════════════════════════════
#  路由
# ═══════════════════════════════════════════════════

API_GET = {
    "/api/analysis/sessions/": api_sessions,
    "/api/analysis/provinces/": api_provinces,
    "/api/analysis/ranking/": api_ranking,
    "/api/analysis/averages/": api_averages,
    "/api/analysis/score-distribution/": api_score_distribution,
    "/api/analysis/teaching-index/": api_teaching_index,
    "/api/students/studios/": api_studios,
    "/api/students/classes/": api_classes,
    "/api/students/": api_students,
    "/api/analysis/groups/": api_groups,
    "/api/jdy/status/": api_sync_status,
}

NOT_SUPPORTED = {"error": "此功能在无 Django 版本中未提供"}


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, relpath):
        if relpath in ("/", "/index.html"):
            relpath = "/index.html"
        full = os.path.normpath(os.path.join(STATIC_DIR, relpath.lstrip("/")))
        if not full.startswith(STATIC_DIR) or not os.path.isfile(full):
            self.send_error(404)
            return
        ext = os.path.splitext(full)[1]
        ctype = {".html": "text/html; charset=utf-8",
                 ".js": "application/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8",
                 ".json": "application/json; charset=utf-8"}.get(ext, "application/octet-stream")
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return {}

    def _read_file(self):
        """解析 multipart/form-data，返回第一个文件字段的字节（无文件返回 None）"""
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return None
        data = self.rfile.read(length)
        ctype = self.headers.get("Content-Type", "")
        m = re.search(r'boundary=([^;]+)', ctype)
        if not m:
            return None
        boundary = m.group(1).strip().strip('"').encode()
        parts = data.split(b"--" + boundary)
        for part in parts:
            if b"filename=" in part:
                body = part.split(b"\r\n\r\n", 1)
                if len(body) == 2:
                    return body[1].rsplit(b"\r\n", 1)[0]
        return None

    def _route(self, method):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") + "/" if parsed.path != "/" else "/"
        qs = parse_qs(parsed.query)
        p = {k: (v[0] if isinstance(v, list) and v else "") for k, v in qs.items()}

        if method == "GET":
            if path in API_GET:
                try:
                    self._send_json(API_GET[path](p))
                except Exception as e:
                    self._send_json({"error": str(e)}, 500)
                return
            self._send_file(path)
            return

        if method == "POST":
            if path == "/api/auth/login/":
                # 无鉴权：任意账号密码均放行
                self._send_json({"token": "nodjango-local"})
                return
            if path == "/api/students/studios/":
                # 兼容某些环境把 studios 当 POST（实际上无需）
                self._send_json(api_studios())
                return
            if path == "/api/jdy/refresh/":
                self._send_json(refresh_cache())
                return
            if path == "/api/exams/import/excel/":
                data = self._read_file()
                if not data:
                    self._send_json({"error": "未收到文件"}, 400)
                    return
                self._send_json(excel_import(data))
                return
            if path == "/api/transition/migrate/":
                self._send_json(transition_migrate(self._read_body()))
                return
            # 其它管理操作：无 Django 版不支持
            self._send_json(NOT_SUPPORTED, 400)
            return

        self._send_json({"error": "method not allowed"}, 405)

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
    if not os.path.isfile(DB_PATH):
        print("未找到 data.db，请确认与 server.py 同目录。")
        sys.exit(1)
    _init_db()
    # 启动时后台自动同步一次（不阻塞服务），之后页面/接口直接读本地缓存
    threading.Thread(target=sync_jdy, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("画室成绩分析系统（无 Django 版）已启动：", flush=True)
    print("   http://localhost:%d" % port, flush=True)
    print("   后台同步简道云中…", flush=True)
    print("   按 Ctrl+C 停止", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
