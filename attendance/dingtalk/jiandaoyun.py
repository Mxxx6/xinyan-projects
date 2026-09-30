"""简道云请假数据 — 外出请假 + 校内请假"""

import logging
import os
import time
import httpx
from datetime import datetime, date, timedelta

logger = logging.getLogger("attendance.jiandaoyun")

API_KEY = os.environ.get("JDY_API_KEY", "")
APP_ID = os.environ.get("JDY_APP_ID", "")
ENTRY_ID = os.environ.get("JDY_ENTRY_ID", "")
BASE = f"https://api.jiandaoyun.com/api/v2/app/{APP_ID}/entry/{ENTRY_ID}/data"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

_cache: list[dict] = []
_cache_time: float = 0
CACHE_TTL = 300


def _fetch_all_27() -> list[dict]:
    global _cache, _cache_time
    now = time.time()
    if _cache and (now - _cache_time) < CACHE_TTL:
        return _cache
    items = []
    skip = 0
    while True:
        try:
            resp = httpx.post(BASE, headers=HEADERS,
                              json={"limit": 200, "skip": skip,
                                    "filter": {"rel": "and", "cond": [
                                        {"field": "xuejie", "type": "text", "method": "eq", "value": ["27"]}
                                    ]}}, timeout=30)
            if resp.status_code != 200:
                break
            batch = resp.json().get("data", [])
            if not batch:
                break
            items.extend(batch)
            skip += len(batch)
        except Exception as e:
            logger.error(f"简道云请求异常: {e}")
            break
    if items:
        _cache = items
        _cache_time = now
        logger.info(f"简道云缓存: {len(items)}条")
    return items


def get_leave_users(target_date: str) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """
    外出请假：学届=27, 销假空, 离校≤今天≤离校+100天, 返校≥明天, 班主任+家长同意 → 全天
    校内请假：学届=27, 校内日期=今天, 班主任+家长同意 → 按时段
    """
    today = date.fromisoformat(target_date)
    tomorrow = today + timedelta(days=1)
    past_100 = today - timedelta(days=100)
    future_100 = today + timedelta(days=100)
    today_cn = today.strftime("%Y/%m/%d")

    out_result: dict[str, set[str]] = {}
    in_result: dict[str, set[str]] = {}

    records = _fetch_all_27()
    if not records:
        return out_result, in_result

    for item in records:
        xh = str(item.get("xuehao", "") or "")
        if not xh:
            continue

        fenlei = str(item.get("userfenlei", "") or "")     # 请假分类：外出/校内
        lxrq_s = str(item.get("lxrq", "") or "")
        fxrq_s = str(item.get("fxrq", "") or "")
        xiaojia = str(item.get("timexiaojia", "") or "")
        bzr = str(item.get("userbzr", "") or "")           # 家长_意见
        fdy = str(item.get("userfdy", "") or "")            # 审批意见(班主任)
        xnrq = str(item.get("xnrq", "") or "")
        xnsd = str(item.get("xnsd", "") or "")

        parent_ok = (bzr == "同意")
        teacher_ok = (fdy == "同意")

        # ── 外出请假：分类=外出 ──
        if fenlei == "外出" and lxrq_s and fxrq_s and not xiaojia and parent_ok and teacher_ok:
            try:
                lxrq = datetime.strptime(lxrq_s[:10], "%Y-%m-%d").date()
                fxrq = datetime.strptime(fxrq_s[:10], "%Y-%m-%d").date()
                if past_100 <= lxrq <= today and tomorrow <= fxrq <= future_100:
                    out_result.setdefault(xh, set()).update(["上午", "中午", "晚上"])
            except ValueError:
                pass

        # ── 校内请假：分类=校内，只需班主任同意 ──
        if fenlei == "校内" and xnrq == today_cn and xnsd and teacher_ok:
            if xh not in in_result:
                in_result[xh] = set()
            # xnsd用"下午"，映射到系统"中午"时段
            if "上午" in xnsd: in_result[xh].add("上午")
            if "下午" in xnsd: in_result[xh].add("中午")
            if "晚上" in xnsd: in_result[xh].add("晚上")

    logger.info(f"简道云: 外出{len(out_result)} 校内{len(in_result)}")
    return out_result, in_result
