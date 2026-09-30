#!/usr/bin/env python3
"""50 new art education low-follower viral cases — Round 2, fresh angles."""

import json, urllib.request, time

API = "http://127.0.0.1:8000/api/analyze"

cases = [
    # ═══ NICHE: 画室老师/画室运营 (10 new cases) ═══
    {
        "title": "盼棠国画-画室猫咪闯入泼墨创作过程",
        "plays": 10170000, "likes": 850000, "comments": 55000, "shares": 180000,
        "duration": 35, "followers": 15000, "niche": "art_studio",
        "tags": "#国画 #泼墨 #猫咪 #画室日常 #创作过程"
    },
    {
        "title": "混子哥画室创作日记-边画边讲故事",
        "plays": 2800000, "likes": 320000, "comments": 28000, "shares": 65000,
        "duration": 48, "followers": 8000, "niche": "art_studio",
        "tags": "#画室日记 #边画边讲 #科普漫画 #创作故事"
    },
    {
        "title": "池州孙老师-九华山边走边画系列",
        "plays": 48100000, "likes": 2210000, "comments": 85000, "shares": 320000,
        "duration": 30, "followers": 50000, "niche": "art_studio",
        "tags": "#边走边画 #九华山 #油画棒 #家乡风景 #教程"
    },
    {
        "title": "教美术的苏苏老师-校园清唱+画画",
        "plays": 5000000, "likes": 1800000, "comments": 120000, "shares": 350000,
        "duration": 25, "followers": 35000, "niche": "art_studio",
        "tags": "#美术老师 #唱歌 #校园 #跨界 #美术+音乐"
    },
    {
        "title": "九匠国风油画-把山水画出东方韵味",
        "plays": 1800000, "likes": 60000, "comments": 3500, "shares": 15000,
        "duration": 38, "followers": 5000, "niche": "art_studio",
        "tags": "#国风油画 #山水 #东方美学 #艺术创作"
    },
    {
        "title": "蓟州董老师-落叶拼老虎零成本创作",
        "plays": 3500000, "likes": 420000, "comments": 32000, "shares": 95000,
        "duration": 42, "followers": 3000, "niche": "art_studio",
        "tags": "#落叶拼画 #零成本创作 #乡土素材 #少儿美术"
    },
    {
        "title": "画室老师唱歌出圈-美术课变身演唱会现场",
        "plays": 6500000, "likes": 850000, "comments": 68000, "shares": 180000,
        "duration": 22, "followers": 12000, "niche": "art_studio",
        "tags": "#美术课 #唱歌 #出圈 #师生互动 #反差"
    },
    {
        "title": "画具打理vlog-调色盘清理过程极度舒适",
        "plays": 1200000, "likes": 180000, "comments": 8500, "shares": 35000,
        "duration": 40, "followers": 2500, "niche": "art_studio",
        "tags": "#画具打理 #调色盘 #解压 #ASMR #画室vlog"
    },
    {
        "title": "矿石自制颜料全过程-复刻独乐寺壁画色彩",
        "plays": 4200000, "likes": 520000, "comments": 38000, "shares": 120000,
        "duration": 55, "followers": 5000, "niche": "art_studio",
        "tags": "#矿石颜料 #独乐寺 #壁画 #传统工艺 #手工制作"
    },
    {
        "title": "画室30天改造记录-从毛坯到最美画室",
        "plays": 5500000, "likes": 680000, "comments": 45000, "shares": 150000,
        "duration": 45, "followers": 8000, "niche": "art_studio",
        "tags": "#画室改造 #装修记录 #30天挑战 #最美画室"
    },

    # ═══ NICHE: 美术集训 (10 new cases) ═══
    {
        "title": "集训素描进步曲线-每10天拍一张对比照",
        "plays": 3800000, "likes": 480000, "comments": 35000, "shares": 85000,
        "duration": 20, "followers": 2000, "niche": "training",
        "tags": "#素描 #进步对比 #美术集训 #成长记录"
    },
    {
        "title": "集训食堂一周伙食真实记录-美术生吃什么",
        "plays": 2200000, "likes": 180000, "comments": 42000, "shares": 35000,
        "duration": 32, "followers": 1500, "niche": "training",
        "tags": "#集训食堂 #美术生伙食 #真实记录 #日常"
    },
    {
        "title": "集训画室最卷同学-凌晨5点就在画板前",
        "plays": 4800000, "likes": 620000, "comments": 55000, "shares": 95000,
        "duration": 18, "followers": 3000, "niche": "training",
        "tags": "#集训 #卷王 #凌晨5点 #美术生 #拼搏"
    },
    {
        "title": "30天速写挑战-从火柴人到满分卷",
        "plays": 2800000, "likes": 350000, "comments": 22000, "shares": 85000,
        "duration": 25, "followers": 2500, "niche": "training",
        "tags": "#速写挑战 #30天 #从零开始 #进步 #美术集训"
    },
    {
        "title": "集训结束那天-全班抱着画板哭的真实记录",
        "plays": 6200000, "likes": 850000, "comments": 75000, "shares": 160000,
        "duration": 35, "followers": 4000, "niche": "training",
        "tags": "#集训结束 #告别 #感动 #美术生 #毕业季"
    },
    {
        "title": "集训画材花费清单-妈妈看完沉默了",
        "plays": 3200000, "likes": 280000, "comments": 48000, "shares": 55000,
        "duration": 28, "followers": 1800, "niche": "training",
        "tags": "#画材花费 #清单 #美术生 #真实开销"
    },
    {
        "title": "色彩静物翻车现场-老师当场气到说不出话",
        "plays": 3500000, "likes": 420000, "comments": 38000, "shares": 65000,
        "duration": 22, "followers": 2000, "niche": "training",
        "tags": "#色彩静物 #翻车 #搞笑 #画室 #师生"
    },
    {
        "title": "集训宿舍深夜突击检查-违禁品大赏",
        "plays": 5500000, "likes": 750000, "comments": 85000, "shares": 140000,
        "duration": 30, "followers": 5000, "niche": "training",
        "tags": "#集训 #宿舍 #突击检查 #违禁品 #搞笑合集"
    },
    {
        "title": "美术生集训前后体重变化-压力肥实录",
        "plays": 1800000, "likes": 220000, "comments": 28000, "shares": 38000,
        "duration": 20, "followers": 1200, "niche": "training",
        "tags": "#集训 #体重 #压力肥 #美术生日常 #真实"
    },
    {
        "title": "素描从50分到90分只用了一个方法-老师独家",
        "plays": 2500000, "likes": 320000, "comments": 18000, "shares": 95000,
        "duration": 28, "followers": 3500, "niche": "training",
        "tags": "#素描 #提分秘籍 #50到90 #独家方法 #联考"
    },

    # ═══ NICHE: 美术生的日常 (10 new cases) ═══
    {
        "title": "柳树林线描画-摆脱焦虑练这个就够了",
        "plays": 850000, "likes": 46000, "comments": 3200, "shares": 15000,
        "duration": 30, "followers": 3000, "niche": "daily",
        "tags": "#线描画 #控笔练习 #摆脱焦虑 #禅绕画 #美术生"
    },
    {
        "title": "灵魂画师-石塑粘土捏卡皮吧啦敲木鱼",
        "plays": 1500000, "likes": 180000, "comments": 15000, "shares": 42000,
        "duration": 35, "followers": 4000, "niche": "daily",
        "tags": "#石塑粘土 #手工 #卡皮吧啦 #丑萌 #治愈"
    },
    {
        "title": "Chuner-人心中的成见是一座大山哪吒丙烯画",
        "plays": 650000, "likes": 22000, "comments": 1800, "shares": 5500,
        "duration": 45, "followers": 2000, "niche": "daily",
        "tags": "#哪吒 #丙烯画 #治愈 #美术生 #电影"
    },
    {
        "title": "美术生通勤路上5分钟画治愈手账",
        "plays": 1200000, "likes": 150000, "comments": 8500, "shares": 35000,
        "duration": 15, "followers": 2000, "niche": "daily",
        "tags": "#通勤画画 #手账 #5分钟 #碎片时间 #治愈"
    },
    {
        "title": "美术生美术校考面试穿什么合集",
        "plays": 2800000, "likes": 220000, "comments": 38000, "shares": 55000,
        "duration": 25, "followers": 3500, "niche": "daily",
        "tags": "#校考 #面试穿搭 #美术生 #合集 #参考"
    },
    {
        "title": "美术生画到崩溃的瞬间合集-笑着笑着就哭了",
        "plays": 4200000, "likes": 550000, "comments": 52000, "shares": 88000,
        "duration": 28, "followers": 2500, "niche": "daily",
        "tags": "#画画崩溃 #搞笑 #共鸣 #美术生日常 #合集"
    },
    {
        "title": "美术生日常-今天临摹莫奈翻车了",
        "plays": 950000, "likes": 68000, "comments": 5500, "shares": 12000,
        "duration": 22, "followers": 1500, "niche": "daily",
        "tags": "#临摹 #莫奈 #翻车 #日常 #美术生"
    },
    {
        "title": "美术生-你看过的动漫vs我画出来的",
        "plays": 3200000, "likes": 480000, "comments": 32000, "shares": 85000,
        "duration": 15, "followers": 3000, "niche": "daily",
        "tags": "#动漫 #二创 #美术生 #对比 #搞笑"
    },
    {
        "title": "美术生学车-教练说你别用画画的握笔法握方向盘",
        "plays": 1800000, "likes": 220000, "comments": 25000, "shares": 42000,
        "duration": 20, "followers": 2000, "niche": "daily",
        "tags": "#美术生学车 #搞笑 #教练 #日常 #反差"
    },
    {
        "title": "美术生买画材的秘密渠道-比淘宝便宜一半",
        "plays": 1500000, "likes": 120000, "comments": 18000, "shares": 55000,
        "duration": 30, "followers": 4000, "niche": "daily",
        "tags": "#画材 #省钱 #秘密渠道 #美术生 #干货"
    },

    # ═══ NICHE: 画室日常/创意绘画 (10 new cases) ═══
    {
        "title": "唐子曦-路边石缝杂草配仓鼠插画治愈200万人",
        "plays": 8500000, "likes": 2000000, "comments": 95000, "shares": 280000,
        "duration": 28, "followers": 50000, "niche": "studio_daily",
        "tags": "#石头缝作画 #街头艺术 #治愈 #仓鼠 #创意"
    },
    {
        "title": "碎片化拍绘画-30秒成品对比+核心笔触展示",
        "plays": 2200000, "likes": 280000, "comments": 12000, "shares": 65000,
        "duration": 30, "followers": 3000, "niche": "studio_daily",
        "tags": "#碎片化 #成品对比 #笔触 #解压 #画画过程"
    },
    {
        "title": "高铁上画画-邻座大爷全程围观最后要了一张",
        "plays": 3500000, "likes": 450000, "comments": 32000, "shares": 75000,
        "duration": 25, "followers": 2500, "niche": "studio_daily",
        "tags": "#高铁画画 #围观 #路人反应 #治愈 #暖"
    },
    {
        "title": "嘉倩壁画工作室-从草图到巨幅壁画全记录",
        "plays": 1800000, "likes": 150000, "comments": 9500, "shares": 42000,
        "duration": 50, "followers": 5000, "niche": "studio_daily",
        "tags": "#壁画 #全记录 #草图到成品 #工作室日常"
    },
    {
        "title": "画室窗外一年四季延时-同一角度不同风景",
        "plays": 4200000, "likes": 580000, "comments": 28000, "shares": 120000,
        "duration": 40, "followers": 3500, "niche": "studio_daily",
        "tags": "#四季 #延时摄影 #画室窗外 #治愈 #时间流逝"
    },
    {
        "title": "用外卖包装盒做调色盘-美术生的省钱发明",
        "plays": 1500000, "likes": 185000, "comments": 15000, "shares": 35000,
        "duration": 20, "followers": 1200, "niche": "studio_daily",
        "tags": "#省钱发明 #外卖盒调色盘 #美术生 #创意"
    },
    {
        "title": "画室停电用手机灯画画-意外发现氛围绝了",
        "plays": 3200000, "likes": 420000, "comments": 22000, "shares": 68000,
        "duration": 22, "followers": 2000, "niche": "studio_daily",
        "tags": "#停电 #手机灯画画 #氛围感 #意外发现"
    },
    {
        "title": "画室水槽-洗笔池的颜色比画还好看",
        "plays": 2800000, "likes": 380000, "comments": 18000, "shares": 55000,
        "duration": 15, "followers": 1800, "niche": "studio_daily",
        "tags": "#洗笔池 #颜料 #意外之美 #画室日常 #治愈"
    },
    {
        "title": "油画创作全过程浓缩60秒-每一笔都是成就感",
        "plays": 1800000, "likes": 220000, "comments": 8500, "shares": 48000,
        "duration": 60, "followers": 4000, "niche": "studio_daily",
        "tags": "#油画创作 #浓缩 #成就感 #画画 #全记录"
    },
    {
        "title": "美术生才懂得快乐-调出一个绝美颜色那一刻",
        "plays": 2500000, "likes": 350000, "comments": 25000, "shares": 55000,
        "duration": 12, "followers": 1500, "niche": "studio_daily",
        "tags": "#调色 #成就感 #美术生的快乐 #日常 #共鸣"
    },

    # ═══ NICHE: 美术艺考 (10 new cases) ═══
    {
        "title": "联考成绩查询现场-全班一起查的窒息3分钟",
        "plays": 8500000, "likes": 1100000, "comments": 95000, "shares": 220000,
        "duration": 35, "followers": 5000, "niche": "art_exam",
        "tags": "#联考查分 #窒息 #真实记录 #美术生 #艺考"
    },
    {
        "title": "美术艺考-我从260分逆袭到全省前100",
        "plays": 3200000, "likes": 420000, "comments": 32000, "shares": 95000,
        "duration": 38, "followers": 3500, "niche": "art_exam",
        "tags": "#逆袭 #联考 #全省前100 #美术生 #励志"
    },
    {
        "title": "校考报名攻略-10个学校怎么排志愿顺序",
        "plays": 1800000, "likes": 150000, "comments": 28000, "shares": 85000,
        "duration": 32, "followers": 4000, "niche": "art_exam",
        "tags": "#校考 #报名 #志愿 #攻略 #美术艺考"
    },
    {
        "title": "美术生联考当天vlog-从凌晨4点起床开始",
        "plays": 5200000, "likes": 680000, "comments": 55000, "shares": 120000,
        "duration": 42, "followers": 4500, "niche": "art_exam",
        "tags": "#联考当天 #vlog #凌晨 #美术生 #真实记录"
    },
    {
        "title": "画了3年终于收到央美录取通知书-开箱全程哭",
        "plays": 6800000, "likes": 950000, "comments": 85000, "shares": 180000,
        "duration": 30, "followers": 6000, "niche": "art_exam",
        "tags": "#央美 #录取通知书 #开箱 #哭了 #美术艺考"
    },
    {
        "title": "美术联考色彩高分卷的秘密-评卷老师告诉你",
        "plays": 2200000, "likes": 280000, "comments": 18000, "shares": 95000,
        "duration": 28, "followers": 5000, "niche": "art_exam",
        "tags": "#色彩 #高分卷 #评卷老师 #秘密 #联考"
    },
    {
        "title": "艺考落榜后我选择了复读-一年后的成绩对比",
        "plays": 3800000, "likes": 520000, "comments": 48000, "shares": 85000,
        "duration": 38, "followers": 3000, "niche": "art_exam",
        "tags": "#复读 #落榜 #逆袭 #对比 #美术艺考"
    },
    {
        "title": "美术生考试翻车名场面-笑着笑着就哭了",
        "plays": 4200000, "likes": 580000, "comments": 52000, "shares": 95000,
        "duration": 25, "followers": 3500, "niche": "art_exam",
        "tags": "#考试翻车 #名场面 #美术生 #搞笑 #艺考"
    },
    {
        "title": "美术艺考花费3年账单-妈妈记的每一笔",
        "plays": 5500000, "likes": 750000, "comments": 88000, "shares": 160000,
        "duration": 35, "followers": 4000, "niche": "art_exam",
        "tags": "#艺考花费 #账单 #妈妈记账 #三年 #感动"
    },
    {
        "title": "美术生选专业避坑-学长含泪总结的5条血泪教训",
        "plays": 2500000, "likes": 320000, "comments": 38000, "shares": 95000,
        "duration": 32, "followers": 5000, "niche": "art_exam",
        "tags": "#选专业 #避坑 #血泪教训 #美术生 #学长总结"
    },
]

def analyze(case):
    data = {k: case[k] for k in ["title","plays","likes","comments","shares","duration","followers","tags"]}
    try:
        req = urllib.request.Request(API, data=json.dumps(data).encode(),
                                       headers={"Content-Type": "application/json"})
        return case, json.loads(urllib.request.urlopen(req, timeout=15).read())
    except Exception as e:
        print(f"  X {case['title'][:30]}... {e}")
        return case, None

results = []
print("="*70)
print("  50条新案例 — Round 2 引擎验证")
print("="*70)

for i, c in enumerate(cases):
    c, r = analyze(c)
    if r:
        vf = r.get("viral_factors", {})
        results.append({
            "title": c["title"], "niche": c["niche"],
            "plays": c["plays"], "likes": c["likes"], "followers": c["followers"],
            "engagement_rate": r["computed"]["interaction_rate"],
            "grade": r["computed"]["grade"],
            "overall_score": vf.get("overall_score", 0),
            "verdict": vf.get("verdict", ""),
        })
    time.sleep(0.12)

# Save
with open("/Users/miao/Desktop/art/art_50_new_results.json", "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# Summary
scores = [r["overall_score"] for r in results]
engs = [r["engagement_rate"] for r in results]
print(f"\nDone: {len(results)}/{len(cases)} validated")
print(f"Avg score: {sum(scores)/len(scores):.0f}  |  Avg engagement: {sum(engs)/len(engs):.2f}%")
s_cnt = sum(1 for r in results if "S" in r["grade"])
a_cnt = sum(1 for r in results if "A" in r["grade"])
print(f"S: {s_cnt}  A: {a_cnt}")

# By niche
from collections import defaultdict
na = defaultdict(lambda: {"scores":[], "count":0})
for r in results:
    na[r["niche"]]["scores"].append(r["overall_score"])
    na[r["niche"]]["count"] += 1
for n, d in sorted(na.items(), key=lambda x: sum(x[1]["scores"])/x[1]["count"], reverse=True):
    print(f"  {n}: {d['count']}条  avg {sum(d['scores'])/d['count']:.0f}")
