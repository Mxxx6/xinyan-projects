#!/usr/bin/env python3
"""
抖音用户主页视频文案提取工具

原理：复用你 Chrome 浏览器里已有的抖音登录态，
     打开目标用户主页，滚动加载视频列表，提取文案。

使用前：
  1. 先在 Chrome 里打开 douyin.com 并登录
  2. pip install playwright && playwright install chromium
  3. 运行 python3 douyin_scraper.py <用户主页链接或抖音号>
"""

import sys
import time
import json
import re
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "douyin_data"
OUTPUT_DIR.mkdir(exist_ok=True)


def extract_user_id(user_input: str) -> str:
    """从链接或抖音号中提取用户标识"""
    # 纯数字 = 抖音号
    if user_input.isdigit():
        return user_input
    # 短链接: https://v.douyin.com/xxx
    if "v.douyin.com" in user_input:
        return user_input  # 需要重定向解析
    # 主页链接: https://www.douyin.com/user/xxx
    m = re.search(r"douyin\.com/user/([A-Za-z0-9_-]+)", user_input)
    if m:
        return m.group(1)
    return user_input


def scrape_with_playwright(user_input: str, max_videos: int = 30):
    """使用 Playwright 控制 Chrome 浏览器抓取"""
    from playwright.sync_api import sync_playwright

    user_id = extract_user_id(user_input)
    print(f"目标: {user_id}")

    with sync_playwright() as p:
        # 用 Playwright 自带的 WebKit (Safari) + 独立用户目录存登录态
        user_dir = Path.home() / ".douyin_scraper_profile"
        user_dir.mkdir(exist_ok=True)

        context = p.webkit.launch_persistent_context(
            user_data_dir=str(user_dir),
            headless=False,
        )

        page = context.new_page()

        # 打开用户主页
        def safe_goto(url):
            """Navigate without waiting for full network idle (Douyin loads forever)."""
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(4)  # Let JS render

        if user_input.startswith("https://v.douyin.com"):
            safe_goto(user_input)
            time.sleep(2)
            final_url = page.url
            print(f"跳转后: {final_url}")
            m = re.search(r"/user/([A-Za-z0-9_-]+)", final_url)
            if m:
                user_id = m.group(1)
                safe_goto(f"https://www.douyin.com/user/{user_id}")
        elif user_id.isdigit():
            safe_goto(f"https://www.douyin.com/user/{user_id}")
        else:
            safe_goto(f"https://www.douyin.com/user/{user_id}")

        time.sleep(3)
        print(f"当前页面: {page.url}")

        # 检查是否需要登录
        if "login" in page.url.lower() or "passport" in page.url.lower():
            print("\n⚠️  需要登录。浏览器窗口已打开，请在浏览器里扫码登录抖音。")
            print("   登录后按回车继续...")
            input()
            # 重新导航到目标页面
            page.goto(page.url, wait_until="networkidle", timeout=30000)
            time.sleep(3)

        print("提取视频数据...")

        # Method 1: Extract from SSR_RENDER_DATA (embedded in HTML)
        videos = []
        html = page.content()
        import re as re2
        # Find RENDER_DATA in script tags
        match = re2.search(r'window\.__SSR_RENDER_DATA__\s*=\s*({.+?});\s*</script>', html, re2.DOTALL)
        if not match:
            match = re2.search(r'<script[^>]*id=\"RENDER_DATA\"[^>]*>(.+?)</script>', html, re2.DOTALL)
        if not match:
            match = re2.search(r'\"aweme_list\"\s*:\s*\[.+?\]', html, re2.DOTALL)

        if match:
            raw = match.group(1) if match.lastindex else match.group(0)
            try:
                data = json.loads(raw) if raw.startswith("{") else json.loads("{" + raw + "}")
                # Navigate to find video list
                def find_videos(obj, depth=0):
                    if depth > 20:
                        return []
                    if isinstance(obj, list):
                        results = []
                        for item in obj:
                            if isinstance(item, dict) and "aweme_id" in item:
                                results.append(item)
                            elif isinstance(item, (dict, list)):
                                results.extend(find_videos(item, depth + 1))
                        return results
                    if isinstance(obj, dict):
                        if "aweme_list" in obj:
                            return obj["aweme_list"]
                        for v in obj.values():
                            r = find_videos(v, depth + 1)
                            if r:
                                return r
                    return []

                items = find_videos(data)
                for aweme in items:
                    vid = str(aweme.get("aweme_id", ""))
                    desc = aweme.get("desc", "")
                    if vid:
                        videos.append({
                            "id": vid,
                            "url": f"https://www.douyin.com/video/{vid}",
                            "text_preview": desc[:300],
                        })
                if videos:
                    print(f"  从页面数据提取到 {len(videos)} 条视频")
            except Exception as e:
                print(f"  解析页面数据失败: {e}")

        # Method 2: Fallback - regex extract from HTML
        if not videos:
            print("  尝试从HTML直接提取...")
            # Extract all video links
            vids = set()
            for m in re2.finditer(r'/(?:video|note)/(\d+)', html):
                vids.add(m.group(1))
            for vid in vids:
                videos.append({
                    "id": vid,
                    "url": f"https://www.douyin.com/video/{vid}",
                    "text_preview": "",
                })
            print(f"  从HTML提取到 {len(videos)} 条视频链接")

        # Method 3: API interception for scroll-loaded content
        api_videos = []

        def collect_videos(response):
            url = response.url
            if "/aweme/" in url and response.status == 200:
                try:
                    data = response.json()
                    for aweme in data.get("aweme_list", []):
                        vid = aweme.get("aweme_id", "")
                        desc = aweme.get("desc", "")
                        if vid and vid not in [v["id"] for v in api_videos]:
                            api_videos.append({
                                "id": vid,
                                "url": f"https://www.douyin.com/video/{vid}",
                                "text_preview": desc[:200],
                            })
                except Exception:
                    pass

        page.on("response", collect_videos)

        # Scroll to load more
        for i in range(8):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)

        # Merge API videos into main list
        existing_ids = {v["id"] for v in videos}
        for av in api_videos:
            if av["id"] not in existing_ids:
                videos.append(av)

        print(f"  共提取 {len(videos)} 条视频")

        # Step 2: Fetch per-video stats via API interception
        # Collect all stats from API responses, keyed by video ID
        all_stats = {}

        def on_response(response):
            url = response.url
            if "/aweme/v1/web/aweme/detail/" in url and response.status == 200:
                try:
                    data = response.json()
                    aweme = data.get("aweme_detail", {})
                    vid = str(aweme.get("aweme_id", ""))
                    s = aweme.get("statistics", {})
                    if vid:
                        # Basic stats
                        entry = {
                            "likes": int(s.get("digg_count", 0)),
                            "comments": int(s.get("comment_count", 0)),
                            "shares": int(s.get("share_count", 0)),
                            "plays": int(s.get("play_count", 0)),
                            "duration": int(aweme.get("duration", 0)) // 1000,
                        }
                        # Full description (longer than the truncated one)
                        full_desc = aweme.get("desc", "")
                        if full_desc:
                            entry["full_desc"] = full_desc
                        # Video content tags
                        video_tag = aweme.get("video_tag", [])
                        if video_tag:
                            entry["video_tags"] = [t.get("tag_name", "") for t in video_tag]
                        # Text extra (hashtags, urls, mentions)
                        text_extra = aweme.get("text_extra", [])
                        if text_extra:
                            entry["text_extra"] = [t.get("hashtag_name", t.get("user_name", "")) for t in text_extra]
                        # Anchor info (product links, mini-program, etc.)
                        anchor = aweme.get("anchor_info", {})
                        if anchor:
                            entry["has_anchor"] = True
                        # Music
                        music = aweme.get("music", {})
                        if music:
                            entry["music"] = music.get("title", "")[:100]
                        # Create time
                        entry["create_time"] = aweme.get("create_time", 0)
                        # Media type
                        entry["media_type"] = aweme.get("media_type", 0)

                        all_stats[vid] = entry
                except Exception:
                    pass

        page.on("response", on_response)

        need_text = [v for v in videos if not v["text_preview"]]
        print(f"\n  逐条打开视频页提取数据（{len(need_text)}条）...")

        for i, v in enumerate(need_text):
            try:
                page.goto(v["url"], wait_until="domcontentloaded", timeout=12000)
                time.sleep(2.5)

                if not v.get("text_preview"):
                    title = page.title()
                    if " - 抖音" in title:
                        title = title.split(" - 抖音")[0].strip()
                    v["text_preview"] = title[:300] if title and title != "抖音" else ""
                    try:
                        desc = page.locator('meta[name="description"]').get_attribute("content")
                        if desc:
                            v["text_preview"] = desc[:300]
                    except Exception:
                        pass

                if (i + 1) % 10 == 0:
                    print(f"    {i+1}/{len(need_text)}...")
            except Exception:
                pass

        # Apply captured stats + content data to videos
        for v in videos:
            vid = v["id"]
            if vid in all_stats:
                entry = all_stats[vid]
                for k in ["plays", "likes", "comments", "shares", "duration", "full_desc",
                           "video_tags", "text_extra", "music", "create_time", "media_type", "has_anchor"]:
                    if k in entry:
                        v[k] = entry[k]

        context.close()

        # Also extract account name
        try:
            acct_name = page.title().split("的抖音")[0] if "的抖音" in page.title() else ""
        except:
            acct_name = ""

        with_stats = sum(1 for v in videos if v.get("likes") is not None)
        with_text = sum(1 for v in videos if v.get("text_preview"))
        # Filter out non-original content (reposts/likes from other accounts)
        if acct_name:
            original = [v for v in videos if acct_name in v.get("text_preview", "")]
            print(f"   过滤后原创: {len(original)} 条（剔除 {len(videos)-len(original)} 条转发）")
            videos = original

        print(f"\n✅ 抓到 {len(videos)} 条原创视频（{with_text}条含文案，{with_stats}条含互动数据）")
        if acct_name:
            print(f"   账号: {acct_name}")
        return videos


def scrape_manual_flow(user_input: str) -> list:
    """
    半自动方案：用你手机/电脑打开用户主页，
    手动复制每条视频链接，脚本去逐个打开提取文案。
    适合 Playwright 搞不定的情况。
    """
    user_id = extract_user_id(user_input)
    print(f"目标: {user_id}")
    print()
    print("请在抖音 App 打开目标用户主页，逐条复制视频链接粘贴过来。")
    print("粘贴完一行回车，空行结束。")
    print()

    links = []
    while True:
        link = input("视频链接> ").strip()
        if not link:
            break
        links.append(link)

    if not links:
        print("没有输入链接。")
        return []

    return fetch_video_texts(links)


def fetch_video_texts(links: list[str]) -> list:
    """用 HTTP 请求获取视频页面中的文案"""
    import urllib.request
    import urllib.error

    results = []
    for i, link in enumerate(links):
        try:
            # 提取视频ID
            m = re.search(r"/video/(\d+)", link)
            vid = m.group(1) if m else link[-20:]

            req = urllib.request.Request(
                f"https://www.douyin.com/video/{vid}" if m else link,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://www.douyin.com/",
                },
            )
            resp = urllib.request.urlopen(req, timeout=10)
            html = resp.read().decode("utf-8", errors="ignore")

            # 从页面提取文案
            texts = []
            # 方法1: 查找 desc 字段
            desc_matches = re.findall(r'"desc"\s*:\s*"([^"]+)"', html)
            texts.extend(desc_matches)
            # 方法2: 查找 title
            title_m = re.search(r"<title>([^<]+)</title>", html)
            if title_m:
                texts.append(title_m.group(1))

            results.append({
                "id": vid,
                "url": link,
                "text": texts[0] if texts else "(未提取到文案)",
                "all_texts": texts,
            })

            print(f"  [{i+1}/{len(links)}] {vid}: {texts[0][:60] if texts else '(空)'}")
            time.sleep(1)

        except urllib.error.HTTPError as e:
            print(f"  [{i+1}/{len(links)}] ❌ HTTP {e.code}")
        except Exception as e:
            print(f"  [{i+1}/{len(links)}] ❌ {e}")

    return results


# ═══ Main ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 douyin_scraper.py <用户主页链接或抖音号>")
        print("  python3 douyin_scraper.py https://v.douyin.com/xxxxx")
        print("  python3 douyin_scraper.py 39013053054")
        print("  python3 douyin_scraper.py --manual")
        sys.exit(1)

    target = sys.argv[1]

    if target == "--manual":
        results = scrape_manual_flow(sys.argv[2] if len(sys.argv) > 2 else "")
    else:
        try:
            from playwright.sync_api import sync_playwright

            results = scrape_with_playwright(target)
        except ImportError:
            print("Playwright 未安装。用半自动模式。")
            print("安装: pip install playwright && playwright install chromium")
            print()
            results = scrape_manual_flow(target)

    if results:
        # 保存结果
        out_file = OUTPUT_DIR / f"douyin_{int(time.time())}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n已保存: {out_file}")
        print(f"共 {len(results)} 条视频")
    else:
        print("\n未抓到任何视频。请尝试 --manual 模式。")
