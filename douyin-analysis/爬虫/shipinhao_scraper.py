#!/usr/bin/env python3
"""
微信视频号内容提取工具

用法：
  python3 shipinhao_scraper.py <视频号主页链接>

使用前：
  1. pip install playwright && playwright install chromium
  2. 运行后浏览器弹出，扫码登录微信视频号
"""

import sys
import time
import json
import re
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "douyin_data"
OUTPUT_DIR.mkdir(exist_ok=True)


def scrape_channel(user_input: str, max_videos: int = 50):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        user_dir = Path.home() / ".shipinhao_scraper_profile"
        user_dir.mkdir(exist_ok=True)

        context = p.chromium.launch_persistent_context(
            user_data_dir=str(user_dir),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.new_page()

        # ── Navigate ──────────────────────────────────────────────────
        if any(d in user_input for d in ["channels.weixin.qq.com", "weixin.qq.com/sph"]):
            target_url = user_input
        else:
            target_url = f"https://channels.weixin.qq.com/channel/{user_input}"

        print(f"目标: {target_url}")

        page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(4)
        print(f"当前页面: {page.url}")

        # ── Login check ───────────────────────────────────────────────
        page_text = page.inner_text("body")[:500] if page.url != "about:blank" else ""
        if "登录" in page_text or "扫码" in page_text or "login" in page.url.lower():
            print()
            print("=" * 50)
            print("请扫码登录微信视频号")
            print("扫码完成后等待页面自动跳转...")
            print("=" * 50)
            # 视频号扫码后页面不自动跳转，等15秒后手动刷新
            print("扫码完成后等待15秒...")
            time.sleep(15)
            print("刷新页面...")
            page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(4)
            current_url = page.url
            print(f"当前页面: {current_url}")

        # ── Intercept API responses ───────────────────────────────────
        all_data = {}

        def on_response(response):
            url = response.url
            # 视频号 API 常见路径
            if response.status != 200:
                return
            try:
                data = response.json()
            except Exception:
                return

            # Path 1: Finder profile feeds
            if "finder" in url and ("feed" in url or "list" in url or "profile" in url):
                _extract_feeds(data, all_data)

            # Path 2: Generic list responses
            if isinstance(data, dict):
                for key in ["data", "feeds", "list", "items", "object", "feed_list", "finder_list"]:
                    if key in data:
                        _extract_feeds(data[key] if isinstance(data[key], dict) else {"list": data[key]}, all_data)
        page.on("response", on_response)

        # ── Scroll to load ────────────────────────────────────────────
        print(f"\n滚动加载中（目标 {max_videos} 条）...")
        last_count = 0
        stuck = 0
        while len(all_data) < max_videos and stuck < 8:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3)
            if len(all_data) > last_count:
                print(f"  已抓到 {len(all_data)} 条...")
                last_count = len(all_data)
                stuck = 0
            else:
                stuck += 1

        # ── Extract from page HTML as fallback ────────────────────────
        if not all_data:
            print("  API未捕获，尝试从页面提取...")
            html = page.content()
            for m in re.finditer(r'(?:export_id|objectId|feed_id)["\']?\s*:["\'](\d+)["\']', html):
                fid = m.group(1)
                if fid not in all_data:
                    all_data[fid] = {"id": fid, "url": f"https://channels.weixin.qq.com/video/feed/{fid}"}
            for m in re.finditer(r'/video/(?:feed|play)/([A-Za-z0-9_-]+)', html):
                fid = m.group(1)
                if fid not in all_data:
                    all_data[fid] = {"id": fid, "url": f"https://channels.weixin.qq.com/video/feed/{fid}"}

        videos = list(all_data.values())

        # ── Visit video pages for missing text ────────────────────────
        need_text = [v for v in videos if not v.get("full_desc") and not v.get("text_preview")]
        if need_text:
            print(f"\n  逐条提取详情（{min(len(need_text), 30)}条）...")
            for i, v in enumerate(need_text[:30]):
                try:
                    if v.get("url"):
                        page.goto(v["url"], wait_until="domcontentloaded", timeout=10000)
                        time.sleep(2)
                        title = page.title()
                        if title and "微信视频号" not in title:
                            v["text_preview"] = title[:300]
                        try:
                            desc = page.locator('meta[name="description"]').get_attribute("content")
                            if desc and len(desc) > 10:
                                v["full_desc"] = desc[:500]
                        except Exception:
                            pass
                    if (i + 1) % 10 == 0:
                        print(f"    {i+1}/{min(len(need_text),30)}...")
                except Exception:
                    pass

        context.close()

        print(f"\n抓取完成: {len(videos)} 条")
        return videos


def _extract_feeds(data, all_data):
    """Extract video feeds from API response data."""
    items = []

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ["list", "feeds", "items", "feed_list", "finder_list", "object_list"]:
            if key in data and isinstance(data[key], list):
                items = data[key]
                break
        # Single feed object
        if not items:
            for key in ["feed", "object", "finder_object"]:
                if key in data and isinstance(data[key], dict):
                    items = [data[key]]
                    break

    for item in items:
        if not isinstance(item, dict):
            continue
        vid = str(item.get("id", item.get("objectId",
                    item.get("export_id", item.get("feed_id", "")))))
        if vid == "":
            continue

        if vid in all_data:
            # Merge new fields
            existing = all_data[vid]
        else:
            existing = {"id": vid}
            all_data[vid] = existing

        # Description
        for dk in ["description", "desc", "title", "displayTitle"]:
            if item.get(dk) and not existing.get("full_desc"):
                existing["full_desc"] = str(item[dk])[:500]
                existing["text_preview"] = str(item[dk])[:200]
                break

        # URL
        if not existing.get("url"):
            existing["url"] = f"https://channels.weixin.qq.com/video/feed/{vid}"

        # Stats
        for lk, vk in [("like_count", "likes"), ("liked_count", "likes"),
                        ("comment_count", "comments"), ("share_count", "shares"),
                        ("play_count", "plays"), ("read_count", "plays"),
                        ("duration", "duration")]:
            if item.get(lk) is not None and vk not in existing:
                existing[vk] = int(item[lk])

        # Tags
        tags = item.get("tags", item.get("video_tags", item.get("topic_list", [])))
        if tags and not existing.get("video_tags"):
            if isinstance(tags, list) and len(tags) > 0:
                if isinstance(tags[0], dict):
                    existing["video_tags"] = [t.get("name", t.get("tag_name", str(t))) for t in tags[:10]]
                else:
                    existing["video_tags"] = [str(t) for t in tags[:10]]

        # Music
        music = item.get("music", item.get("bgm", {}))
        if isinstance(music, dict) and music.get("title") and not existing.get("music"):
            existing["music"] = str(music["title"])[:100]

        # Author
        author = item.get("author", item.get("finder", item.get("contact", {})))
        if isinstance(author, dict):
            if not existing.get("author_name"):
                existing["author_name"] = str(author.get("nickname", author.get("name", "")))[:50]

        # Media type / duration
        for mk in ["media_type", "duration", "create_time", "createtime", "height", "width"]:
            if item.get(mk) is not None and mk not in existing:
                existing[mk] = item[mk]


# ═══ Main ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 shipinhao_scraper.py <视频号主页链接>")
        print()
        print("示例:")
        print("  python3 shipinhao_scraper.py https://channels.weixin.qq.com/channel/xxxxx")
        print("  python3 shipinhao_scraper.py https://channels.weixin.qq.com/finder/xxxxx")
        sys.exit(1)

    results = scrape_channel(sys.argv[1])

    if results:
        out_file = OUTPUT_DIR / f"shipinhao_{int(time.time())}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n已保存: {out_file}")
        print(f"共 {len(results)} 条视频")

        # Show preview
        with_text = sum(1 for v in results if v.get("full_desc") or v.get("text_preview"))
        with_stats = sum(1 for v in results if v.get("likes", 0) > 0)
        print(f"含文案: {with_text}  含互动数据: {with_stats}")
    else:
        print("\n未抓到任何视频。")
        print("提示:")
        print("  1. 确保链接正确")
        print("  2. 确保已扫码登录")
        print("  3. 手动滚动页面后再重试")
