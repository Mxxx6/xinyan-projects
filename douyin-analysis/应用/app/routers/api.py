"""JSON data API endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import get_session
from app.models.schemas import OverviewOut, TrendPoint, MessageOut

router = APIRouter(prefix="/api", tags=["API"])


async def _get_data_service(session: AsyncSession):
    """Return the appropriate data service based on demo/real mode."""
    if settings.demo_mode:
        from app.services.mock_data import MockDataGenerator
        return MockDataGenerator()
    else:
        from app.services.douyin_client import DouyinClient
        return DouyinClient()


@router.get("/overview", response_model=OverviewOut)
async def get_overview(session: AsyncSession = Depends(get_session)):
    """Get aggregate KPI totals for the dashboard overview."""
    if settings.demo_mode:
        from app.services.mock_data import MockDataGenerator
        svc = MockDataGenerator()
    else:
        from app.services.douyin_client import DouyinClient
        svc = DouyinClient()
    data = await svc.get_overview(session)
    return OverviewOut(**data)


@router.get("/trends")
async def get_trends(
    days: int = Query(default=30, ge=7, le=90, description="Number of days"),
    session: AsyncSession = Depends(get_session),
):
    """Get daily aggregated time series for charts."""
    if settings.demo_mode:
        from app.services.mock_data import MockDataGenerator
        svc = MockDataGenerator()
    else:
        from app.services.douyin_client import DouyinClient
        svc = DouyinClient()
    return await svc.get_trends(session, days=days)


@router.get("/videos")
async def get_videos(
    sort: str = Query(default="engagement", description="Sort: engagement, plays, latest"),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Get ranked video list."""
    if settings.demo_mode:
        from app.services.mock_data import MockDataGenerator
        svc = MockDataGenerator()
    else:
        from app.services.douyin_client import DouyinClient
        svc = DouyinClient()
    return await svc.get_videos(session, sort=sort, limit=limit)


@router.get("/video/{video_id}")
async def get_video_detail(
    video_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get single video detail with daily breakdown."""
    if settings.demo_mode:
        from app.services.mock_data import MockDataGenerator
        svc = MockDataGenerator()
    else:
        from app.services.douyin_client import DouyinClient
        svc = DouyinClient()
    result = await svc.get_video_detail(session, video_id)
    if result is None:
        return {"error": "视频不存在"}
    return result


@router.get("/hotspot")
async def get_hotspot(session: AsyncSession = Depends(get_session)):
    """Get trending / hotspot analysis."""
    if settings.demo_mode:
        from app.services.mock_data import MockDataGenerator
        svc = MockDataGenerator()
    else:
        from app.services.douyin_client import DouyinClient
        svc = DouyinClient()
    return await svc.get_hotspot(session)


@router.get("/posting-hours")
async def get_posting_hours(session: AsyncSession = Depends(get_session)):
    """Get engagement distribution by posting hour."""
    if settings.demo_mode:
        from app.services.mock_data import MockDataGenerator
        svc = MockDataGenerator()
    else:
        from app.services.douyin_client import DouyinClient
        svc = DouyinClient()
    return await svc.get_posting_hour_distribution(session)


@router.post("/refresh", response_model=MessageOut)
async def refresh_data(session: AsyncSession = Depends(get_session)):
    """Trigger a data refresh from the API (or regenerate mock data)."""
    if settings.demo_mode:
        from app.services.mock_data import MockDataGenerator
        from sqlalchemy import text
        # Clear existing data and re-seed
        await session.execute(text("DELETE FROM daily_stats"))
        await session.execute(text("DELETE FROM videos"))
        await session.execute(text("DELETE FROM app_config WHERE key = 'data_seeded'"))
        gen = MockDataGenerator()
        await gen.seed_database(session)
        await session.commit()
        return MessageOut(success=True, message="演示数据已重新生成")
    else:
        from app.services.douyin_client import DouyinClient
        client = DouyinClient()
        result = await client.refresh_all_data(session)
        return MessageOut(success=True, message=f"已刷新 {result} 条视频数据")


from pydantic import BaseModel, Field

class VideoAnalysisRequest(BaseModel):
    title: str = ""
    plays: int = Field(..., ge=0, description="播放量")
    likes: int = Field(..., ge=0, description="点赞数")
    comments: int = Field(..., ge=0, description="评论数")
    shares: int = Field(..., ge=0, description="分享数")
    duration: int = Field(default=0, ge=0, description="视频时长(秒)")
    followers: int = Field(default=0, ge=0, description="账号粉丝数(可选)")
    tags: str = Field(default="", description="话题标签，逗号分隔")


@router.post("/analyze")
async def analyze_video(req: VideoAnalysisRequest):
    """投入单条视频数据，返回完整分析报告。"""
    from app.services.analytics import AnalyticsEngine

    eng = AnalyticsEngine

    # 1. 核心指标
    interaction_rate = eng.engagement_rate(req.likes, req.comments, req.shares, req.plays)
    like_rate = round(req.likes / req.plays * 100, 2) if req.plays > 0 else 0.0
    comment_rate = round(req.comments / req.plays * 100, 2) if req.plays > 0 else 0.0
    share_rate = round(req.shares / req.plays * 100, 2) if req.plays > 0 else 0.0

    # 2. 互动率评级
    if interaction_rate >= 10:
        grade = "S 级 · 现象级爆款"
        grade_color = "#ef4444"
    elif interaction_rate >= 5:
        grade = "A 级 · 优秀内容"
        grade_color = "#f59e0b"
    elif interaction_rate >= 3:
        grade = "B 级 · 良好水平"
        grade_color = "#10b981"
    elif interaction_rate >= 1:
        grade = "C 级 · 一般表现"
        grade_color = "#6366f1"
    else:
        grade = "D 级 · 需要优化"
        grade_color = "#6b7280"

    # 3. 互动结构诊断
    total_interactions = req.likes + req.comments + req.shares
    like_pct = round(req.likes / total_interactions * 100, 1) if total_interactions > 0 else 0
    comment_pct = round(req.comments / total_interactions * 100, 1) if total_interactions > 0 else 0
    share_pct = round(req.shares / total_interactions * 100, 1) if total_interactions > 0 else 0

    # 诊断建议
    suggestions = []
    if like_pct > 90:
        suggestions.append("⚠️ 点赞占比过高(>90%)，评论和分享偏少——内容「好看但没讨论度」，尝试在结尾抛一个争议性问题引导评论")
    if share_pct < 2:
        suggestions.append("🔴 分享率极低(<2%)，内容缺乏社交货币。加一句「转发给你的XX」或制造「只有XX才懂」的圈层认同")
    if comment_pct < 3:
        suggestions.append("🟡 评论率偏低(<3%)，试试在视频里埋一个「故意说错」的点，用户会忍不住纠正你")
    if req.duration > 60 and interaction_rate < 3:
        suggestions.append("⏱ 视频偏长(>60秒)且互动低，考虑压缩到30秒以内，完播率对算法权重极高")
    if req.duration <= 15 and interaction_rate >= 5:
        suggestions.append("✅ 短视频(<15秒)+高互动，是抖音算法最偏好的组合，继续这个方向")
    if not suggestions:
        suggestions.append("✅ 互动结构健康，继续当前策略")

    # 4. 粉丝转化效率（如果有粉丝数）
    fan_conversion = None
    if req.followers > 0:
        fan_conversion = round(req.likes / req.followers * 100, 2)
        if fan_conversion > 20:
            suggestions.append(f"🔥 赞粉比高达{fan_conversion}%，明显出圈了——大量非粉丝在互动，建议追投DOU+放大")
        elif fan_conversion < 1:
            suggestions.append(f"📉 赞粉比仅{fan_conversion}%，粉丝都没刷到？检查是否被限流或标签没打对")

    # 5. 话题标签分析
    tag_list = [t.strip() for t in req.tags.replace("#", "").split() if t.strip()] if req.tags else []
    tag_advice = ""
    if tag_list:
        if len(tag_list) > 5:
            tag_advice = f"标签偏多({len(tag_list)}个)，抖音推荐3-5个精准标签效果更好"
        elif len(tag_list) < 2:
            tag_advice = "标签太少，建议补到3-5个，覆盖：赛道大词+细分词+场景词"
        else:
            tag_advice = f"标签数量({len(tag_list)}个)合理"

    # ── 6. 爆款因子归因分析 ──────────────────────────────────────
    # Five-factor model: Hook · Social Currency · Emotion · Algorithm · Topic
    factors = []

    # Factor 1: Hook Strength (钩子力)
    if req.duration <= 30:
        if like_rate >= 8:
            hook_score = 90 + (like_rate - 8) * 2
            hook_note = f"超高点赞率({like_rate}%)，前3秒钩子极强，用户看到就忍不住点❤️"
        elif like_rate >= 5:
            hook_score = 65 + (like_rate - 5) * 8
            hook_note = f"点赞率良好({like_rate}%)，钩子有效但还有优化空间"
        else:
            hook_score = max(20, like_rate * 12)
            hook_note = f"点赞率偏低({like_rate}%)，前3秒钩子可能不够抓人——试试「否定常识」或「结果前置」"
    else:
        if like_rate >= 5:
            hook_score = 70
            hook_note = f"长视频({req.duration}s)仍保持{like_rate}%点赞率，内容质量过硬"
        else:
            hook_score = 40
            hook_note = f"长视频({req.duration}s)+低点赞率，开头可能拖沓，建议把最炸的画面放第1秒"

    factors.append({
        "name": "钩子力",
        "icon": "🎣",
        "score": min(round(hook_score), 100),
        "summary": hook_note,
        "what_to_learn": "他能火的一个关键原因是什么？前3秒用了哪种钩子？是「结果前置」还是「反常识」还是「悬念」？模仿这种开头结构，换到你的内容上",
    })

    # Factor 2: Social Currency (社交货币)
    if share_pct >= 5:
        share_score = 85 + share_pct
        share_note = f"分享率极高({share_pct}%)，用户转发是因为「我也是」的认同感或「快看这个」的资讯价值"
        share_learn = "这条内容给了用户一个「身份标签」——转发它等于告诉别人「我懂游戏」「我是三角洲玩家」。你的内容能不能让粉丝转发后觉得有面子？"
    elif share_pct >= 2:
        share_score = 55 + share_pct * 8
        share_note = f"分享率中等({share_pct}%)，有一定传播力但还没到裂变级别"
        share_learn = "看看评论区——转发的人说了什么？是@了朋友还是发到群里？找到那个传播动机然后放大它"
    else:
        share_score = max(10, share_pct * 15)
        share_note = f"分享率低({share_pct}%)，内容「值得看但不值得转」——缺少社交传播的理由"
        share_learn = "在视频最后加一句「艾特你的队友」「转发给总摸鱼的那个」——给用户一个转发动作的明确指令"

    factors.append({
        "name": "社交货币",
        "icon": "💰",
        "score": min(round(share_score), 100),
        "summary": share_note,
        "what_to_learn": share_learn,
    })

    # Factor 3: Emotional Trigger (情绪触发)
    if comment_pct >= 4:
        emotion_score = 85 + comment_pct * 2
        emotion_note = f"评论率很高({comment_pct}%)，内容触发了强烈的讨论欲——要么有争议、要么有共鸣、要么有疑问"
        emotion_learn = "翻他的评论区，看热评前10条在讨论什么。找到那个「争议点」或「共鸣点」，你的内容也可以围绕这个点做"
    elif comment_pct >= 1.5:
        emotion_score = 55 + comment_pct * 7
        emotion_note = f"评论率中等({comment_pct}%)，有一定讨论度但还不够热"
        emotion_learn = "看看他是怎么引导评论的？标题提问？内容里埋梗？结尾抛话题？学会用「故意说错」「让大家选A还是B」来激发评论"
    else:
        emotion_score = max(10, comment_pct * 20)
        emotion_note = f"评论率低({comment_pct}%)，用户看完就走了——缺少「忍不住想说一句」的钩子"
        emotion_learn = "在视频里故意留一个「信息缺口」——比如「第三点我放在评论区了」「你们觉得呢？」——人天生有填补缺口的冲动"

    factors.append({
        "name": "情绪触发",
        "icon": "💥",
        "score": min(round(emotion_score), 100),
        "summary": emotion_note,
        "what_to_learn": emotion_learn,
    })

    # Factor 4: Algorithm Fit (算法适配)
    algo_score = 70
    algo_reasons = []
    if req.duration <= 15:
        algo_score += 15
        algo_reasons.append("≤15秒(完播率最高档)")
    elif req.duration <= 30:
        algo_score += 10
        algo_reasons.append("≤30秒(算法推荐甜区)")
    elif req.duration <= 60:
        algo_score += 0
        algo_reasons.append("31-60秒(需高完播支撑)")
    else:
        algo_score -= 15
        algo_reasons.append(f">{60}s(长视频天然完播低)")

    if interaction_rate >= 10:
        algo_score += 20
        algo_reasons.append("互动率>10%(算法强推信号)")
    elif interaction_rate >= 5:
        algo_score += 10
        algo_reasons.append("互动率>5%(进入更大流量池)")
    else:
        algo_reasons.append(f"互动率{interaction_rate}%(流量池受限)")

    if like_pct < 95:
        algo_score += 5
        algo_reasons.append("互动类型多元(点赞+评论+分享均衡，算法加权)")

    algo_note = " · ".join(algo_reasons)
    algo_learn = "抖音算法最看重三个信号：完播率(时长控制)、互动率(点赞评转总量)、互动多样性(不能只有赞)。对标竞品的数据，找到你被算法「扣分」最多的那个指标，优先优化"

    factors.append({
        "name": "算法适配",
        "icon": "🤖",
        "score": min(round(algo_score), 100),
        "summary": algo_note,
        "what_to_learn": algo_learn,
    })

    # Factor 5: Topic Heat (赛道热度)
    topic_score = 60
    topic_note = ""
    topic_learn = ""
    if not tag_list:
        topic_score = 40
        topic_note = "无标签数据，无法评估赛道"
    else:
        # Keyword-based topic heat estimation
        gaming_keywords = ["游戏", "行动", "猛攻", "战场", "吃鸡", "赛季", "排位", "枪", "刀", "皮肤", "抽卡"]
        entertainment_keywords = ["搞笑", "挑战", "日常", "vlog", "段子"]
        knowledge_keywords = ["教程", "干货", "方法", "技巧", "学会", "攻略"]
        fashion_keywords = ["穿搭", "美妆", "护肤", "发型", "OOTD"]
        food_keywords = ["美食", "做饭", "吃", "探店", "食谱", "火锅"]

        all_text = (req.title + " " + req.tags).lower()
        hit_categories = []
        if any(kw in all_text for kw in gaming_keywords):
            hit_categories.append(("游戏", 85, "游戏赛道天然高互动，玩家习惯点赞评论，但竞争激烈"))
        if any(kw in all_text for kw in entertainment_keywords):
            hit_categories.append(("娱乐", 75, "泛娱乐赛道流量大但粉丝粘性低，容易爆但难持续"))
        if any(kw in all_text for kw in knowledge_keywords):
            hit_categories.append(("知识", 70, "知识类长尾效应强，搜索流量占比高，但冷启动慢"))
        if any(kw in all_text for kw in fashion_keywords):
            hit_categories.append(("时尚穿搭", 65, "穿搭赛道分享率高，适合带货，但需视觉质量"))
        if any(kw in all_text for kw in food_keywords):
            hit_categories.append(("美食", 68, "美食赛道受众广，时段效应明显(饭点流量高)"))

        if hit_categories:
            cat_name, cat_score, cat_detail = sorted(hit_categories, key=lambda x: x[1], reverse=True)[0]
            topic_score = cat_score
            topic_note = f"赛道：{cat_name}。{cat_detail}"
            topic_learn = f"他在「{cat_name}」赛道里，这个赛道的爆款公式往往有规律可循。去看看他其他视频的标题结构和发布时间，找他的「爆款模板」"
        else:
            topic_score = 55
            topic_note = "无法自动识别赛道，建议手动判断"
            topic_learn = "去他主页看他发过哪些话题，找到播放最高的3条，归纳共同点"

    factors.append({
        "name": "赛道热度",
        "icon": "🔥",
        "score": min(round(topic_score), 100),
        "summary": topic_note,
        "what_to_learn": topic_learn,
    })

    # Overall viral score (weighted average)
    weights = {"钩子力": 0.25, "社交货币": 0.20, "情绪触发": 0.20, "算法适配": 0.20, "赛道热度": 0.15}
    overall = sum(f["score"] * weights[f["name"]] for f in factors)

    return {
        "title": req.title or "未命名视频",
        "core_metrics": {
            "plays": req.plays,
            "likes": req.likes,
            "comments": req.comments,
            "shares": req.shares,
            "duration_seconds": req.duration,
        },
        "computed": {
            "interaction_rate": interaction_rate,
            "like_rate": like_rate,
            "comment_rate": comment_rate,
            "share_rate": share_rate,
            "grade": grade,
            "grade_color": grade_color,
        },
        "interaction_structure": {
            "like_pct": like_pct,
            "comment_pct": comment_pct,
            "share_pct": share_pct,
            "total": total_interactions,
        },
        "suggestions": suggestions,
        "fan_conversion": fan_conversion,
        "tag_analysis": {
            "tags": tag_list,
            "advice": tag_advice,
        },
        "viral_factors": {
            "factors": factors,
            "overall_score": round(overall),
            "verdict": (
                "顶级爆款 🔥🔥🔥 五个维度全面在线"
                if overall >= 80 else
                "强爆款潜力 🔥🔥 大部分因子突出，少量可优化"
                if overall >= 65 else
                "中等传播力 🔥 有亮点但短板也明显"
                if overall >= 45 else
                "传播力偏弱 多个因子需要系统优化"
            ),
        },
    }


# ── OCR endpoint ─────────────────────────────────────────────────────

import re
import io
import base64

class OCRRequest(BaseModel):
    image_base64: str = ""

@router.post("/analyze/ocr")
async def ocr_screenshot(req: OCRRequest):
    """Upload a screenshot, OCR the numbers, return parsed video data."""
    image_base64 = req.image_base64
    try:
        from PIL import Image
    except ImportError:
        return {"error": "Pillow 未安装", "ocr_available": False}

    # Decode image
    img_bytes = None
    if image_base64:
        # Strip data:image/... prefix if present
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]
        try:
            img_bytes = base64.b64decode(image_base64)
        except Exception:
            return {"error": "图片解码失败"}

    if not img_bytes:
        return {"error": "请提供图片"}

    try:
        img = Image.open(io.BytesIO(img_bytes))

        # Try macOS native Vision OCR first, fall back to tesseract
        text = ""
        try:
            from app.services.ocr_mac import ocr_image_bytes
            import io as _io
            buf = _io.BytesIO(img_bytes)
            # Save to temp and OCR
            import tempfile as _tf
            with _tf.NamedTemporaryFile(suffix=".png", delete=False) as _f:
                _f.write(img_bytes)
                _tmp = _f.name
            from app.services.ocr_mac import ocr_image
            text = ocr_image(_tmp)
            import os as _os
            _os.unlink(_tmp)
        except Exception as _e:
            # Fallback to tesseract
            try:
                import pytesseract
                text = pytesseract.image_to_string(img, lang="chi_sim+eng")
            except Exception:
                raise RuntimeError(f"OCR 失败 (Vision: {_e})")

        # Parse numbers from OCR output
        result = _parse_ocr_text(text)

        result["ocr_raw"] = text.strip()
        result["ocr_available"] = True
        return result

    except Exception as e:
        return {"error": f"OCR 失败: {str(e)}", "ocr_available": False}


def _parse_ocr_text(text: str) -> dict:
    """Extract video metrics from OCR'd text using pattern matching."""
    data = {
        "title": "",
        "plays": 0,
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "favorites": 0,
        "duration": 0,
    }

    # Step 1: Extract all number tokens with their surrounding context
    # Find all {number}{万|w} patterns and their line context
    tokens = []
    for m in re.finditer(r"(\d+\.?\d*)\s*([万w])", text):
        val = int(float(m.group(1)) * 10000)
        # Get surrounding context (20 chars before this number)
        start = max(0, m.start() - 20)
        ctx = text[start:m.end()].lower()
        tokens.append({"value": val, "context": ctx, "raw": m.group(0)})

    # Also match plain numbers (no 万/w) that could be counts
    for m in re.finditer(r"(?<!\d)(\d{4,})(?!\d)", text):
        val = int(m.group(1))
        if val >= 100:  # meaningful count
            start = max(0, m.start() - 20)
            ctx = text[start:m.end()].lower()
            # Avoid duplicates with 万/w values
            if not any(abs(t["value"] - val) < val * 0.1 for t in tokens):
                tokens.append({"value": val, "context": ctx, "raw": m.group(1)})

    # Step 2: Match tokens to fields by context keywords
    keyword_map = {
        "plays": ["播放", "观看", "播", "play"],
        "likes": ["点赞", "赞", "like"],
        "comments": ["评论", "评", "comment"],
        "shares": ["分享", "转发", "享", "share"],
        "favorites": ["收藏", "藏", "favor"],
    }

    assigned = set()
    for field, keywords in keyword_map.items():
        for token in tokens:
            if token["value"] in assigned:
                continue
            if any(kw in token["context"] for kw in keywords):
                data[field] = token["value"]
                assigned.add(token["value"])
                break

    # Step 3: For unassigned tokens, use size heuristic
    unassigned = [t for t in tokens if t["value"] not in assigned]
    unassigned.sort(key=lambda t: t["value"], reverse=True)

    # On Douyin: plays is the largest, then likes, then shares ≈ comments
    # The order: plays > likes > shares > comments
    if unassigned:
        # If plays not matched, assign largest
        if data["plays"] == 0 and len(unassigned) >= 4:
            data["plays"] = unassigned[0]["value"]
            data["likes"] = unassigned[1]["value"]
            data["shares"] = unassigned[2]["value"]  # usually 2nd or 3rd largest
            data["comments"] = unassigned[3]["value"]
            if len(unassigned) >= 5:
                data["favorites"] = unassigned[4]["value"]
        elif data["plays"] == 0 and len(unassigned) >= 3:
            data["likes"] = unassigned[0]["value"]
            data["comments"] = unassigned[1]["value"]
            data["shares"] = unassigned[2]["value"]

    return data