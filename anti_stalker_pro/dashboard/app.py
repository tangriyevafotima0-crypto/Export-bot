"""FastAPI dashboard application for the Anti-Stalker Intelligence System.

Provides a web interface with REST API endpoints, WebSocket real-time updates,
JWT authentication, and a static HTML/JS frontend.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.config import get_settings
from core.logger import get_logger
from dashboard.auth import create_access_token, verify_token

logger = get_logger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    logger.info("Dashboard starting up")
    yield
    logger.info("Dashboard shutting down")


def create_dashboard_app() -> FastAPI:
    """Create and configure the FastAPI dashboard application.

    Returns:
        FastAPI: Fully configured application with all routes mounted.
    """
    app = FastAPI(
        title="Anti-Stalker Intelligence Dashboard",
        description="Real-time stalker monitoring and analytics dashboard",
        version="1.0.0",
        lifespan=lifespan,
    )

    settings = get_settings()
    dashboard_origin = f"http://localhost:{settings.dashboard_port}"

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[dashboard_origin, "http://localhost:8080"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from dashboard.routes.analytics import router as analytics_router
    from dashboard.routes.targets import router as targets_router
    from dashboard.routes.reports import router as reports_router
    from dashboard.routes.realtime import router as realtime_router

    app.include_router(analytics_router)
    app.include_router(targets_router)
    app.include_router(reports_router)
    app.include_router(realtime_router)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    class LoginRequest(BaseModel):
        """Login request body."""
        password: str

    @app.post("/api/auth/login")
    async def login(request: LoginRequest) -> JSONResponse:
        """Authenticate user with the dashboard secret key.

        Args:
            request: Login request containing the password.

        Returns:
            JSONResponse: JWT access token on success.
        """
        settings = get_settings()
        if request.password != settings.admin_password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        token = create_access_token(data={"sub": "admin", "role": "admin"})
        return JSONResponse(content={"access_token": token, "token_type": "bearer"})

    @app.get("/api/auth/verify")
    async def verify_auth(token: str) -> dict:
        """Verify a JWT token is valid.

        Args:
            token: JWT token to verify.
        """
        payload = verify_token(token)
        return {"valid": True, "user": payload.get("sub")}

    @app.get("/", response_class=HTMLResponse)
    async def serve_dashboard() -> HTMLResponse:
        """Serve the main dashboard HTML page."""
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
        return HTMLResponse(
            content="<h1>Dashboard</h1><p>Static files not found.</p>",
            status_code=200,
        )

    @app.get("/health")
    async def health_check() -> dict:
        """Health check endpoint."""
        return {"status": "healthy", "service": "anti-stalker-dashboard"}

    return app
