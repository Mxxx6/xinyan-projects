#!/usr/bin/env python3
"""
一键分析截图 → 生成 PDF 报告

用法：把抖音截图放到 screenshots/ 文件夹，然后运行：
    python3 analyze_screenshots.py

输出：report.pdf
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import urllib.request

# ── Config ────────────────────────────────────────────────────────────
API_BASE = "http://127.0.0.1:8000"
SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"
OUTPUT_PDF = Path(__file__).parent / "report.pdf"


def ocr_image(image_path: str) -> dict:
    """Send image to OCR API, return parsed data."""
    import base64
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    req = urllib.request.Request(
        f"{API_BASE}/api/analyze/ocr",
        data=json.dumps({"image_base64": b64}).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


def analyze_data(data: dict) -> dict:
    """Send parsed data to analysis API, return full report."""
    req = urllib.request.Request(
        f"{API_BASE}/api/analyze",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


# ── PDF Generator ─────────────────────────────────────────────────────

def generate_pdf(reports: list[dict], output_path: str):
    """Generate a Chinese-language PDF report from analysis results."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()

    # ── Use built-in font + try Noto Sans SC ──
    font_name = "Helvetica"
    font_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    cn_font = None
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                pdf.add_font("CJK", "", fp, uni=True)
                cn_font = "CJK"
                break
            except Exception:
                continue

    if cn_font is None:
        print("⚠️ 未找到中文字体，PDF 中文将显示为空白。")
        cn_font = "Helvetica"

    # ── Title page ────────────────────────────────────────────────────
    pdf.set_font(cn_font, "", 24)
    pdf.cell(0, 20, "抖音视频分析报告", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font(cn_font, "", 12)
    pdf.cell(0, 10, f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.cell(0, 10, f"共分析 {len(reports)} 条视频", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)

    # ── Each video ────────────────────────────────────────────────────
    for idx, r in enumerate(reports):
        # Page break between videos (except first)
        if idx > 0:
            pdf.add_page()

        vf = r.get("viral_factors", {})
        factors = vf.get("factors", [])

        # Title
        pdf.set_font(cn_font, "", 16)
        title = r.get("title", "未命名视频")
        pdf.cell(0, 12, f"#{idx+1}  {title}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        # Grade badge
        comp = r.get("computed", {})
        grade = comp.get("grade", "N/A")
        pdf.set_font(cn_font, "", 14)
        pdf.cell(0, 10, f"评级：{grade}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        # Core metrics table
        cm = r.get("core_metrics", {})
        pdf.set_font(cn_font, "", 10)
        metrics = [
            ("播放量", f"{cm.get('plays', 0):,}"),
            ("点赞", f"{cm.get('likes', 0):,}"),
            ("评论", f"{cm.get('comments', 0):,}"),
            ("分享", f"{cm.get('shares', 0):,}"),
            ("互动率", f"{comp.get('interaction_rate', 0)}%"),
            ("时长", f"{cm.get('duration_seconds', 0)}s"),
        ]
        for i, (label, value) in enumerate(metrics):
            col = i % 3
            x = 10 + col * 60
            y_offset = 0 if i < 3 else 8
            pdf.set_xy(x, pdf.get_y() + y_offset)
            pdf.set_font(cn_font, "", 9)
            pdf.cell(55, 6, f"{label}：{value}")

        pdf.ln(20)

        # Viral factors
        if factors:
            pdf.set_font(cn_font, "", 13)
            pdf.cell(0, 10, "爆款因子归因", new_x="LMARGIN", new_y="NEXT")
            overall = vf.get("overall_score", 0)
            verdict = vf.get("verdict", "")
            pdf.set_font(cn_font, "", 10)
            pdf.cell(0, 7, f"综合评分：{overall}/100 — {verdict}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

            for f in factors:
                name = f.get("name", "")
                icon = f.get("icon", "")
                score = f.get("score", 0)
                summary = f.get("summary", "")
                learn = f.get("what_to_learn", "")

                # Factor header
                pdf.set_font(cn_font, "", 11)
                bar_filled = "█" * (score // 10)
                bar_empty = "░" * (10 - score // 10)
                pdf.cell(0, 7, f"{icon} {name}：{score}/100  {bar_filled}{bar_empty}", new_x="LMARGIN", new_y="NEXT")

                # Summary
                pdf.set_font(cn_font, "", 9)
                pdf.set_x(14)
                pdf.multi_cell(170, 5, f"分析：{summary}")
                pdf.ln(1)

                # Learn
                pdf.set_x(14)
                pdf.set_font(cn_font, "", 9)
                pdf.multi_cell(170, 5, f"借鉴：{learn}")
                pdf.ln(4)

        # Suggestions
        suggestions = r.get("suggestions", [])
        if suggestions:
            pdf.set_font(cn_font, "", 11)
            pdf.cell(0, 8, "诊断建议", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(cn_font, "", 9)
            for s in suggestions:
                pdf.set_x(14)
                pdf.multi_cell(170, 5, f"• {s}")
            pdf.ln(4)

    # ── Footer ────────────────────────────────────────────────────────
    pdf.set_font(cn_font, "", 8)
    pdf.set_y(-15)
    pdf.cell(0, 10, "由抖音数据分析平台自动生成  |  Demo模式数据仅供参考", align="C")

    pdf.output(output_path)
    return output_path


# ── Main ──────────────────────────────────────────────────────────────

def main():
    # Check server
    try:
        urllib.request.urlopen(f"{API_BASE}/", timeout=3)
    except Exception:
        print("❌ 请先启动服务：python3 run.py")
        sys.exit(1)

    # Find screenshots
    images = sorted(SCREENSHOTS_DIR.glob("*"))
    images = [f for f in images if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".heic")]

    if not images:
        print(f"❌ 没有找到截图，请把图片放到 {SCREENSHOTS_DIR}")
        sys.exit(1)

    print(f"📸 找到 {len(images)} 张截图\n")

    reports = []
    for i, img_path in enumerate(images):
        print(f"[{i+1}/{len(images)}] {img_path.name}")

        # Step 1: OCR
        try:
            ocr_result = ocr_image(str(img_path))
        except Exception as e:
            print(f"  ❌ OCR失败: {e}")
            continue

        if ocr_result.get("error"):
            print(f"  ❌ {ocr_result['error']}")
            continue

        print(f"  OCR: 播放={ocr_result.get('plays',0):,} 点赞={ocr_result.get('likes',0):,} "
              f"评论={ocr_result.get('comments',0):,} 分享={ocr_result.get('shares',0):,}")

        # Step 2: Analyze
        if not ocr_result.get("likes"):
            print("  ⚠️ 未识别到有效数据，跳过")
            continue

        try:
            analysis = analyze_data(ocr_result)
        except Exception as e:
            print(f"  ❌ 分析失败: {e}")
            continue

        grade = analysis.get("computed", {}).get("grade", "?")
        score = analysis.get("viral_factors", {}).get("overall_score", "?")
        print(f"  评级: {grade} | 综合评分: {score}/100")
        reports.append(analysis)
        print()

    if not reports:
        print("❌ 没有成功分析的视频")
        sys.exit(1)

    # Step 3: Generate PDF
    print(f"📄 生成 PDF 报告...")
    output = generate_pdf(reports, str(OUTPUT_PDF))
    print(f"✅ 报告已生成：{output}")
    print(f"   共 {len(reports)} 条视频分析")


if __name__ == "__main__":
    main()
