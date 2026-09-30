"""学生名单与打卡记录匹配"""

from datetime import datetime
from typing import Optional, Set
from .rules import classify_status


def match_attendance(
    students: list[dict],
    records: list[dict],
    class_start: datetime,
    early_minutes: int = 30,
    late_grace_minutes: int = 5,
    leave_user_ids: Optional[Set[str]] = None,
) -> list[dict]:
    record_map: dict[str, dict] = {}
    for r in records:
        uid = r["user_id"]
        if uid not in record_map or r["check_in_time"] < record_map[uid]["check_in_time"]:
            record_map[uid] = r

    results = []
    for s in students:
        rec = record_map.get(s["user_id"])
        check_in = rec["check_in_time"] if rec else None
        is_makeup = rec.get("is_makeup", False) if rec else False
        makeup_time = rec.get("makeup_time", "") if rec else ""

        status, label = classify_status(check_in, class_start, early_minutes, late_grace_minutes)
        results.append({
            "student_user_id": s["user_id"], "student_name": s["name"],
            "job_number": s.get("job_number", ""), "dept_name": s.get("dept_name", ""),
            "check_in_time": check_in, "is_makeup": is_makeup,
            "makeup_time": makeup_time, "status": status, "label": label,
        })
    return results
