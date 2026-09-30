"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models.database import init_db


templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    await init_db()

    # If demo mode, seed mock data on first run
    from app.config import settings
    if settings.demo_mode:
        from app.models.database import async_session
        from sqlalchemy import text
        async with async_session() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM videos"))
            count = result.scalar()
            if count == 0:
                from app.services.mock_data import MockDataGenerator
                gen = MockDataGenerator()
                await gen.seed_database(session)
                await session.commit()

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="抖音数据分析仪表盘",
        description="Douyin Video Analytics Dashboard",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Static files
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # Register routers
    from app.routers import dashboard, api
    app.include_router(dashboard.router)
    app.include_router(api.router)

    return app


app = create_app()
