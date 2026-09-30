"""出勤状态判定 — 基于钉钉 timeResult 原始结果"""

from datetime import datetime
from typing import Optional

STATUS_ORDER = {"absent": 1, "leave_out": 2, "leave_in": 3, "makeup": 4, "on_time": 5}

STATUS_LABELS = {
    "on_time": "✅ 出勤",
    "absent": "❌ 缺卡",
    "leave_out": "🚶 外出请假",
    "leave_in": "🏫 在校请假",
    "makeup": "🔧 已补卡",
}


def classify_status(
    check_in_time: Optional[str],
    time_result: str = "",
    deadline: Optional[datetime] = None,
    early_minutes: int = 30,
    late_grace_minutes: int = 0,
) -> tuple[str, str]:
    """判定：有打卡=出勤，无打卡=缺卡"""
    if check_in_time is None:
        return ("absent", "❌ 缺卡")

    tr = time_result or ""

    if tr == "Leave":
        return ("leave_out", "🚶 外出请假")
    elif tr == "NotSigned":
        return ("absent", "❌ 缺卡")

    return ("on_time", "✅ 出勤")


def _fmt_student(r: dict) -> str:
    parts = []
    jn = r.get("job_number", "")
    dn = r.get("dept_name", "")
    if jn:
        parts.append(f"[{jn}]")
    parts.append(r["student_name"])
    if dn:
        parts.append(f"({dn})")
    return "".join(parts)


def generate_report(
    class_name: str,
    class_date: str,
    class_start: str,
    results: list[dict],
) -> str:
    results = sorted(results, key=lambda r: STATUS_ORDER.get(r["status"], 99))

    absent = [r for r in results if r["status"] == "absent"]
    leave_out = [r for r in results if r["status"] == "leave_out"]
    leave_in = [r for r in results if r["status"] == "leave_in"]
    makeup = [r for r in results if r["status"] == "makeup"]
    on_time = [r for r in results if r["status"] == "on_time"]

    total = len(results)
    present = len(on_time) + len(leave_out) + len(leave_in) + len(makeup)
    rate = f"{present / total * 100:.0f}%" if total > 0 else "N/A"

    lines = [
        f"📋 **{class_name} 出勤报告** ({class_date} {class_start})",
        "━━━━━━━━━━━━━━━━━━━━",
    ]

    if absent:
        names = '、'.join(_fmt_student(r) for r in absent[:30])
        more = f" ...等{len(absent)}人" if len(absent) > 30 else ""
        lines.append(f"")
        lines.append(f"❌ **缺卡 {len(absent)}人**：{names}{more}")

    if leave_out:
        lines.append(f"")
        lines.append(f"🚶 **外出请假 {len(leave_out)}人**：{'、'.join(_fmt_student(r) for r in leave_out)}")

    if leave_in:
        lines.append(f"")
        lines.append(f"🏫 **在校请假 {len(leave_in)}人**：{'、'.join(_fmt_student(r) for r in leave_in)}")

    if makeup:
        names = '、'.join(_fmt_student(r) for r in makeup[:20])
        more = f" ...等{len(makeup)}人" if len(makeup) > 20 else ""
        lines.append(f"")
        lines.append(f"🔧 **已补卡 {len(makeup)}人**：{names}{more}")

    lines.append(f"")
    lines.append(f"✅ **出勤 {len(on_time)}人**")

    lines.extend([
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📊 出勤率：**{rate}** ({present}/{total})",
    ])
    return "\n".join(lines)
