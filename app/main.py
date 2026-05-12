"""
FastAPI application factory.

Exposes `app` as the ASGI entry point. Run with:

    uvicorn app.main:app --reload

Production:

    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger, setup_logging
from app.db.session import engine

logger = get_logger(__name__)


# ── Lifespan: replaces deprecated @app.on_event("startup"/"shutdown") ──────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hooks."""
    setup_logging()
    logger.info(
        "Starting %s v%s in %s mode",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ENVIRONMENT,
    )
    yield
    # Clean up the DB connection pool on shutdown
    await engine.dispose()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Application factory pattern — easier to test and reuse."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        lifespan=lifespan,
        # Hide docs in production unless DEBUG is on
        docs_url="/docs"
        if settings.DEBUG or settings.ENVIRONMENT != "production"
        else None,
        redoc_url="/redoc"
        if settings.DEBUG or settings.ENVIRONMENT != "production"
        else None,
    )

    # ── Middleware ────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ────────────────────────────────────────────────
    @app.exception_handler(AppException)
    async def handle_app_exception(_: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(
        _: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception("Unhandled exception")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    # ── Routes ────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health", tags=["meta"])
    async def health_check() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok", "version": settings.APP_VERSION}

    @app.get("/", tags=["meta"], include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
        }

    return app


# ASGI entry point picked up by uvicorn / gunicorn
app = create_app()
