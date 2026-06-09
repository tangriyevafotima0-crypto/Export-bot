"""Dashboard route modules."""

from dashboard.routes.analytics import router as analytics_router
from dashboard.routes.targets import router as targets_router
from dashboard.routes.reports import router as reports_router
from dashboard.routes.realtime import router as realtime_router

__all__ = ["analytics_router", "targets_router", "reports_router", "realtime_router"]
