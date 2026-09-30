#!/usr/bin/env python3
"""Clean compact PDF for 500 cases."""

import json, os
from datetime import datetime
from collections import defaultdict
from fpdf import FPDF

with open("/Users/miao/Desktop/art/内容军火库/数据/art_500_results.json") as f:
    results = json.load(f)

cn_font = None
for fp in ["/System/Library/Fonts/STHeiti Light.ttc","/System/Library/Fonts/PingFang.ttc"]:
    if os.path.exists(fp): cn_font = fp; break

sorted_results = sorted(results, key=lambda r: r["overall_score"], reverse=True)
scores = [r["overall_score"] for r in results]
engs = [r["engagement_rate"] for r in results]
confirmed = [r for r in results if r.get("account")]
s_n = sum(1 for r in results if "S" in r["grade"])
a_n = sum(1 for r in results if "A" in r["grade"])

pdf = FPDF()
pdf.set_auto_page_break(True, 12)
pdf.add_font("C", "", cn_font)
M = 10; W = 190

def h1(t, sz=14):
    pdf.ln(4); pdf.set_font("C","",sz); pdf.set_x(M)
    pdf.cell(W, 8, t, new_x="LMARGIN", new_y="NEXT"); pdf.ln(1)

def p(t, sz=8):
    pdf.set_font("C","",sz); pdf.set_x(M)
    pdf.multi_cell(W, 4.2, t); pdf.set_x(M)

def h2(t, sz=10):
    pdf.set_font("C","",sz); pdf.set_x(M)
    pdf.cell(W, 6, t, new_x="LMARGIN", new_y="NEXT")

# ═══ PAGE 1 ═══
pdf.add_page()
pdf.ln(4)
pdf.set_font("C","",22)
pdf.cell(W, 10, "美术赛道低粉爆款分析报告", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.set_font("C","",11)
pdf.cell(W, 7, "500案例 x 8赛道 x 4内容类型 x 五因子模型", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.set_font("C","",7)
pdf.cell(W, 5, f"{datetime.now().strftime('%Y-%m-%d %H:%M')} | [Y]=真实账号可查 [P]=爆款公式模式样本 | 赛道:画室/集训/日常/画室日常/艺考/艺考规划/高考美术/美术老师", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.ln(5)

h1("一、总览")
p(f"500条 | 可查{len(confirmed)}条 | 均分{sum(scores)/len(scores):.0f} | 均互动率{sum(engs)/len(engs):.2f}% | S级{s_n} A级{a_n}")

# Niche table
h1("二、8赛道排名")
na = defaultdict(lambda: {"s":[],"e":[],"c":0,"y":0})
for r in results:
    n=r["niche"]; na[n]["s"].append(r["overall_score"]); na[n]["e"].append(r["engagement_rate"]); na[n]["c"]+=1
    if r.get("account"): na[n]["y"]+=1

pdf.set_font("C","",7)
cw=[8,40,24,24,28,24]; hd=["","赛道","数量","均分","均互率","可查"]
for j,h in enumerate(hd): pdf.cell(cw[j],5,h,border=1,align="C")
pdf.ln()
for i,(n,d) in enumerate(sorted(na.items(),key=lambda x:sum(x[1]["s"])/x[1]["c"],reverse=True)):
    row=[f"[{i+1}]",n,str(d["c"]),f"{sum(d['s'])/d['c']:.0f}",f"{sum(d['e'])/d['c']:.2f}%",str(d["y"])]
    for j,v in enumerate(row): pdf.cell(cw[j],5,v,border=1,align="C")
    pdf.ln()

# Type table
pdf.ln(3); h2("4内容类型排名")
ct=defaultdict(lambda: {"s":[],"c":0})
for r in results: t=r["content_type"]; ct[t]["s"].append(r["overall_score"]); ct[t]["c"]+=1
cw2=[8,40,24,24,28]
for j,h in enumerate(["","类型","数量","均分","均互率"]): pdf.cell(cw2[j],5,h,border=1,align="C")
pdf.ln()
for i,(t,d) in enumerate(sorted(ct.items(),key=lambda x:sum(x[1]["s"])/x[1]["c"],reverse=True)):
    row=[f"[{i+1}]",t,str(d["c"]),f"{sum(d['s'])/d['c']:.0f}",f"{sum(d['s'])/d['c']:.0f}"]
    for j,v in enumerate(row): pdf.cell(cw2[j],5,v,border=1,align="C")
    pdf.ln()

# ═══ PAGE 2: Matrix + TOP 30 ═══
pdf.add_page()
h1("三、赛道x类型矩阵(均分)")
niches=["画室","美术集训","美术生的日常","画室日常","美术艺考","艺考规划","高考美术","美术老师"]
types=["整活","教学","口播","画画"]
matrix=defaultdict(lambda: defaultdict(lambda: {"s":[],"c":0}))
for r in results: matrix[r["niche"]][r["content_type"]]["s"].append(r["overall_score"]); matrix[r["niche"]][r["content_type"]]["c"]+=1

cw3=[34,39,39,39,39]
pdf.set_font("C","",7)
for j,h in enumerate([""]+types): pdf.cell(cw3[j],5,h,border=1,align="C")
pdf.ln()
for niche in niches:
    pdf.cell(cw3[0],5,niche,border=1,align="C")
    for j,tp in enumerate(types):
        d=matrix[niche][tp]
        v=f"{sum(d['s'])/d['c']:.0f}" if d["c"]>0 else "-"
        pdf.cell(cw3[j+1],5,v,border=1,align="C")
    pdf.ln()

# TOP 30
pdf.ln(4)
h1("四、TOP 30")
top30=sorted_results[:30]
cw4=[6,78,28,20,20,20,18]
pdf.set_font("C","",6)
for j,h in enumerate(["#","标题","赛道","类型","互率","评分","出处"]): pdf.cell(cw4[j],4,h,border=1,align="C")
pdf.ln()
for i,r in enumerate(top30):
    src="Y" if r.get("account") else "P"
    row=[str(i+1),r["title"][:38],r["niche"][:5],r["content_type"],f"{r['engagement_rate']:.0f}%",str(r["overall_score"]),src]
    for j,v in enumerate(row): pdf.cell(cw4[j],4,v,border=1,align="C" if j>0 else "C")
    pdf.ln()

# ═══ PAGE 3-4: Source accounts ═══
pdf.add_page()
h1("五、可查出处账号")
accts=defaultdict(list)
for r in results:
    if r.get("account"): accts[r["account"]].append(r)
p(f"共{len(confirmed)}条标注了可查账号，覆盖{len(accts)}个真实创作者。",8)
pdf.ln(2)
pdf.set_font("C","",7)
for acct, items in sorted(accts.items(),key=lambda x:len(x[1]),reverse=True):
    s=items[0]
    pdf.set_x(M); pdf.cell(38,4,acct)
    pdf.cell(0,4,f"关联{len(items)}条 | {s['source'][:75]}",new_x="LMARGIN",new_y="NEXT")

# ═══ Complete 500 ═══
pdf.ln(4)
h1("六、完整500条列表")
pdf.set_font("C","",6)
pdf.cell(W,4,"[Y]=可查真实账号 [P]=模式样本  按综合评分降序排列",new_x="LMARGIN",new_y="NEXT")
pdf.ln(2)

cw5=[7,80,24,18,16,16,12,17]
headers=["#","标题","赛道","类型","互率","评分","级","出处"]
for j,h in enumerate(headers): pdf.cell(cw5[j],4,h,border=1,align="C")
pdf.ln()

count=0
for i,r in enumerate(sorted_results):
    src="Y" if r.get("account") else "P"
    row=[str(i+1),r["title"][:40],r["niche"][:5],r["content_type"],f"{r['engagement_rate']:.0f}%",str(r["overall_score"]),r["grade"][:1],src]
    for j,v in enumerate(row): pdf.cell(cw5[j],3.5,v,border=1,align="C" if j>0 else "C")
    pdf.ln()
    count+=1

# Footer
pdf.set_font("C","",6)
pdf.set_y(-10)
pdf.cell(W,6,f"美术赛道500条 | {datetime.now().strftime('%Y-%m-%d')}",align="C")

out="/Users/miao/Desktop/art/内容军火库/报告/美术赛道500条分析报告.pdf"
pdf.output(out)
print(f"Done: {out} ({pdf.pages_count} pages)")
