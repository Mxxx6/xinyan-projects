#!/usr/bin/env python3
"""上平素描 38条原创视频文案梳理"""

import json, os, re
from datetime import datetime
from collections import Counter
from fpdf import FPDF

import glob as _g

f = max(_g.glob("/Users/miao/Desktop/art/内容军火库/数据/douyin_data/*.json"), key=os.path.getmtime)
with open(f) as fp:
    data = json.load(fp)

real = [v for v in data if v.get("likes", 0) > 0]

cn_font = None
for fp in ["/System/Library/Fonts/STHeiti Light.ttc", "/System/Library/Fonts/PingFang.ttc"]:
    if os.path.exists(fp):
        cn_font = fp
        break

pdf = FPDF()
pdf.set_auto_page_break(True, 14)
pdf.add_font("C", "", cn_font)
M = 10
W = 190


def h1(t):
    pdf.ln(3)
    pdf.set_font("C", "", 14)
    pdf.set_x(M)
    pdf.cell(W, 8, t, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def h2(t):
    pdf.ln(1)
    pdf.set_font("C", "", 11)
    pdf.set_x(M)
    pdf.cell(W, 6, t, new_x="LMARGIN", new_y="NEXT")


def p(t, sz=8):
    pdf.set_font("C", "", sz)
    pdf.set_x(M)
    pdf.multi_cell(W, 4.2, t)
    pdf.set_x(M)


# ═══ PAGE 1: Summary ═══
pdf.add_page()
pdf.ln(4)
pdf.set_font("C", "", 20)
pdf.cell(W, 10, "上平素描 · 文案选题库", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.set_font("C", "", 10)
pdf.cell(W, 6, "38条原创视频文案梳理  |  用于竞品对标与选题参考", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.ln(6)

# Stats
dates_list = []
likes_list = []
for v in real:
    txt = v["text_preview"]
    m = re.search(r"(\d{4})(\d{2})(\d{2})发布", txt)
    if m:
        dates_list.append(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))))
    m2 = re.search(r"([\d.]+)万?个喜欢", txt)
    if m2:
        likes_list.append(float(m2.group(1)))

if dates_list:
    dates_list.sort()
    span = (max(dates_list) - min(dates_list)).days

h1("账号数据总览")
p(f"账号: 上平素描（清美上平） | 原创视频: {len(real)} 条")
p(f"时间: {min(dates_list).strftime('%Y-%m-%d')} ~ {max(dates_list).strftime('%Y-%m-%d')}（{span}天）")
p(f"发布频率: {len(real) / max(span / 30, 1):.1f} 条/月 | 约 {span / len(real):.0f} 天/条")
if likes_list:
    p(f"最高点赞: {max(likes_list):.0f}万 | 最低: {min(likes_list):.0f}万 | 平均: {sum(likes_list) / len(likes_list):.1f}万")

# Tags
all_tags = []
for v in real:
    tags = re.findall(r"#(\S+)", v["text_preview"])
    all_tags.extend(tags)
tag_cnt = Counter(all_tags)
top_tags = tag_cnt.most_common(8)

pdf.ln(2)
h2("常用标签")
p("  ".join([f"#{t}({c}次)" for t, c in top_tags]))

# Title formula
pdf.ln(2)
h2("标题公式")
p('所有标题共用同一结构: [痛点问题 或 结果承诺] + 感叹号 + 标签堆叠')
p('典型: "XXX怎么办？一条视频给你讲清楚！"')
p('      "掌握这个能力，胜过盲目练习十年！"')
p('      "学会XXX，素描立马开悟！"')
p('      "想用好XXX？一定要注意这三点！"')

# ═══ PAGE 2+: All 38 captions ═══
pdf.add_page()
h1(f"{len(real)}条视频（按点赞热度排序）")

p(f'数据来源: 逐条打开视频页，拦截API返回的真实互动数据。最高点赞{max(v.get("likes",0) for v in real):,}，最低{min(v.get("likes",0) for v in real):,}。播放量暂未获取到（抖音独立接口）。', 7)
pdf.ln(2)

# Sort by date extracted from text
def extract_date(v):
    m = re.search(r"(\d{4})(\d{2})(\d{2})发布", v["text_preview"])
    if m:
        return m.group(0)
    return "9999"


real_sorted = sorted(real, key=lambda v: v.get("likes", 0), reverse=True)

for i, v in enumerate(real_sorted):
    txt = v["text_preview"]

    # Extract key parts
    date_str = ""
    m = re.search(r"(\d{4})(\d{2})(\d{2})发布", txt)
    if m:
        date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    likes = v.get("likes", 0)
    comments = v.get("comments", 0)
    shares = v.get("shares", 0)
    stats_line = f"赞{likes:,}  评{comments:,}  分享{shares:,}"

    # Title part (before first dash)
    title_part = txt.split(" - ")[0].strip()
    # Remove date suffix from title
    title_part = re.sub(r"于\d{8}发布.*$", "", title_part).strip()

    # Tags
    tags = re.findall(r"#(\S+)", txt)
    tags_str = "  ".join([f"#{t}" for t in tags[:6]])

    pdf.set_font("C", "", 7)
    pdf.set_x(M)
    pdf.cell(6, 4, str(i + 1))
    pdf.set_font("C", "", 8)
    pdf.cell(0, 4, f"{stats_line}  |  {date_str}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("C", "", 9)
    pdf.set_x(M + 2)
    pdf.multi_cell(W - 2, 4.5, title_part)
    pdf.set_x(M)

    pdf.set_font("C", "", 7)
    pdf.set_x(M + 6)
    pdf.cell(0, 4, tags_str[:150], new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)

# ═══ Last page: Insights ═══
pdf.add_page()
h1("选题方向分类")

categories = {
    "工具/材料": ["炭笔", "铅笔", "工具"],
    "揉擦技巧": ["揉擦"],
    "排线/笔触": ["排线"],
    "暗部处理": ["暗部"],
    "深入塑造": ["塑造", "深入"],
    "衬布/背景": ["衬布", "背景"],
    "头发画法": ["头发"],
    "画面补救": ["糊", "脏", "灰"],
    "核心概念": ["宁方勿圆", "收形", "主动"],
    "考学指导": ["考学", "考研", "艺考"],
    "大师学习": ["大师"],
    "综合提升": ["画技", "猛涨", "开悟", "方法", "能力"],
}

cat_count = Counter()
for v in real:
    txt = v["text_preview"].split("！")[0].split("？")[0]
    matched = False
    for cat, keywords in categories.items():
        if any(kw in txt for kw in keywords):
            cat_count[cat] += 1
            matched = True
            break
    if not matched:
        cat_count["其他技巧"] += 1

for cat, cnt in cat_count.most_common():
    bar = "|" * cnt
    pdf.set_font("C", "", 8)
    pdf.set_x(M)
    pdf.cell(30, 4, cat)
    pdf.cell(0, 4, f"{bar}  {cnt}条", new_x="LMARGIN", new_y="NEXT")

pdf.ln(4)
h1("可复用的爆款标题模板")
templates = [
    '"XXX怎么办？一条视频给你讲清楚！"',
    '"学会XXX，素描立马开悟！"',
    '"掌握这个能力，胜过盲目练习十年！"',
    '"XXX画不好？原来是XX顺序搞错了！"',
    '"想用好XXX，一定要注意这三点！"',
    '"三招教会你XXX！"',
    '"认真听完X分钟，你的画技会猛涨！"',
    '"XXX技巧大公开！看到就是赚到！"',
]
for t in templates:
    pdf.set_font("C", "", 9)
    pdf.set_x(M + 4)
    pdf.cell(4, 5, "-")
    pdf.cell(0, 5, t, new_x="LMARGIN", new_y="NEXT")

pdf.ln(3)
p("提示: 上平素描的标题风格偏「权威老师」型（笃定、不解释、直接给结论）。如果你的定位是「亲近学长」型——可以用同样的标题结构，但把语气放软：「很多人画不好暗部，其实就三个原因」「我当年揉擦也糊，后来发现是这一步做反了」。", 8)

# Footer
pdf.set_font("C", "", 6)
pdf.set_y(-12)
pdf.cell(W, 6, "上平素描文案选题库 | 38条原创 | 竞品对标分析 | " + datetime.now().strftime("%Y-%m-%d"), align="C")

out = "/Users/miao/Desktop/art/内容军火库/报告/上平素描视频数据报告.pdf"
pdf.output(out)
print(f"Done: {out} ({pdf.pages_count} pages)")
