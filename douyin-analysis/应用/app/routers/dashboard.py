"""HTML page routes."""

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.main import templates
from app.models.database import get_session

router = APIRouter(tags=["Pages"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main dashboard page."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "demo_mode": settings.demo_mode,
        "title": "数据仪表盘",
    })


@router.get("/videos", response_class=HTMLResponse)
async def videos_page(request: Request):
    """Full video list page."""
    return templates.TemplateResponse("videos.html", {
        "request": request,
        "demo_mode": settings.demo_mode,
        "title": "视频列表",
    })


@router.get("/analyze", response_class=HTMLResponse)
async def analyze_page(request: Request):
    """Single video analysis tool page."""
    return templates.TemplateResponse("analyze.html", {
        "request": request,
        "demo_mode": settings.demo_mode,
        "title": "视频分析",
    })


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings and configuration page."""
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "demo_mode": settings.demo_mode,
        "title": "系统设置",
        "client_key_configured": bool(settings.douyin_client_key),
    })


@router.post("/settings")
async def save_settings(
    request: Request,
    demo_mode: str = Form(default="true"),
    client_key: str = Form(default=""),
    client_secret: str = Form(default=""),
):
    """Save settings from the settings form."""
    # In a real app we'd persist these. For demo, we update in-memory.
    settings.demo_mode = demo_mode == "true"
    if client_key:
        settings.douyin_client_key = client_key
    if client_secret:
        settings.douyin_client_secret = client_secret

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "demo_mode": settings.demo_mode,
        "title": "系统设置",
        "client_key_configured": bool(settings.douyin_client_key),
        "saved": True,
    })
