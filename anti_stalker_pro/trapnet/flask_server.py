"""Flask-based tracking link server for the trap network.

Provides HTTP endpoints that capture visitor information (IP, User-Agent,
referer, fingerprint data) when tracking links are visited. Serves a
redirect page with embedded JavaScript for browser fingerprinting.
"""

import asyncio
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, request, Response

from core.config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)

# Reference to the main asyncio event loop, set by the caller before starting Flask
_main_loop: Optional[asyncio.AbstractEventLoop] = None
_main_loop_lock = threading.Lock()


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Set the main asyncio event loop reference for async bridge calls.

    Must be called from the main thread before starting the Flask server
    in a background thread.

    Args:
        loop: The main asyncio event loop.
    """
    global _main_loop
    with _main_loop_lock:
        _main_loop = loop
    logger.info("Main event loop reference set for Flask async bridge")


def create_flask_app() -> Flask:
    """Create and configure the Flask trap server application.

    Sets up routes for tracking link capture and fingerprint data
    collection. CORS is disabled to avoid detection.

    Returns:
        Flask: Configured Flask application instance.
    """
    app = Flask(__name__)
    settings = get_settings()
    app.config["SECRET_KEY"] = settings.dashboard_secret_key

    @app.route("/<tracking_code>", methods=["GET"])
    def track_visit(tracking_code: str) -> Response:
        """Handle a visit to a tracking link.

        Captures visitor IP, User-Agent, referer, and serves a redirect
        page with embedded fingerprinting JavaScript.

        Args:
            tracking_code: The unique tracking code from the URL.

        Returns:
            Response: HTML page with redirect and fingerprint script.
        """
        visitor_ip = _get_real_ip()
        user_agent = request.headers.get("User-Agent", "")
        referer = request.headers.get("Referer", "")

        logger.info(
            f"Tracking link visited: code={tracking_code}, "
            f"ip={visitor_ip}, ua={user_agent[:80]}"
        )

        _store_visit_async(
            link_id=tracking_code,
            visitor_ip=visitor_ip,
            user_agent=user_agent,
            referer=referer,
        )

        from trapnet.fingerprinter import Fingerprinter
        fingerprinter = Fingerprinter()
        html_page = fingerprinter.generate_tracking_page(
            tracking_code=tracking_code,
            redirect_url=settings.tracking_redirect_url,
        )

        return Response(html_page, mimetype="text/html")

    @app.route("/api/fingerprint", methods=["POST"])
    def receive_fingerprint() -> Response:
        """Receive browser fingerprint data from the tracking page JavaScript.

        Processes the fingerprint payload and updates the corresponding
        BioLinkVisit record with device information.

        Returns:
            Response: Empty 204 response to minimize suspicion.
        """
        data = request.get_json(silent=True)
        if not data:
            return Response(status=204)

        tracking_code = data.get("tracking_code", "")
        fingerprint_data = data.get("fingerprint", {})
        visitor_ip = _get_real_ip()

        logger.info(
            f"Fingerprint received: code={tracking_code}, ip={visitor_ip}"
        )

        _update_fingerprint_async(
            link_id=tracking_code,
            visitor_ip=visitor_ip,
            device_info=fingerprint_data,
        )

        return Response(status=204)

    @app.after_request
    def remove_cors_headers(response: Response) -> Response:
        """Remove CORS headers to minimize detection footprint.

        Args:
            response: The Flask response object.

        Returns:
            Response: Modified response without CORS headers.
        """
        response.headers.pop("Access-Control-Allow-Origin", None)
        response.headers.pop("Access-Control-Allow-Methods", None)
        response.headers.pop("Access-Control-Allow-Headers", None)
        return response

    return app


def _get_real_ip() -> str:
    """Extract the real visitor IP address from the request.

    Checks X-Forwarded-For and X-Real-IP headers for proxied requests,
    falls back to remote_addr.

    Returns:
        str: The visitor's IP address.
    """
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP", "")
    if real_ip:
        return real_ip.strip()
    return request.remote_addr or "0.0.0.0"


def _store_visit_async(
    link_id: str,
    visitor_ip: str,
    user_agent: str,
    referer: str,
) -> None:
    """Store a tracking link visit in the database asynchronously.

    Creates a BioLinkVisit record with the captured visitor information.
    Uses asyncio.run_coroutine_threadsafe to schedule work on the main
    event loop from the Flask thread. Falls back to synchronous SQLite
    insertion if the async bridge is unavailable.

    Args:
        link_id: The tracking link code.
        visitor_ip: Visitor's IP address.
        user_agent: Visitor's User-Agent string.
        referer: Visitor's referer URL.
    """
    with _main_loop_lock:
        loop = _main_loop

    if loop is not None and loop.is_running():
        future = asyncio.run_coroutine_threadsafe(
            _store_visit(link_id, visitor_ip, user_agent, referer),
            loop,
        )
        # Add a callback to log errors from the future
        future.add_done_callback(_log_future_exception)
    else:
        logger.warning(
            "Main event loop not available; using synchronous fallback for %s",
            link_id,
        )
        _store_visit_sync(link_id, visitor_ip, user_agent, referer)


def _log_future_exception(future) -> None:
    """Log any exception from a completed Future.

    Args:
        future: The completed Future object.
    """
    try:
        exc = future.exception()
        if exc is not None:
            logger.error(f"Async visit storage failed: {exc}", exc_info=exc)
    except (asyncio.CancelledError, asyncio.InvalidStateError):
        pass


def _store_visit_sync(
    link_id: str,
    visitor_ip: str,
    user_agent: str,
    referer: str,
) -> None:
    """Synchronous fallback for storing visits directly via sqlite3.

    Used when the main event loop is not available. Bypasses SQLAlchemy
    async and writes directly to the SQLite database file.

    Args:
        link_id: The tracking link code.
        visitor_ip: Visitor's IP address.
        user_agent: Visitor's User-Agent string.
        referer: Visitor's referer URL.
    """
    try:
        settings = get_settings()
        db_url = settings.database_url
        # Extract the file path from the async SQLite URL
        # Format: sqlite+aiosqlite:///path/to/db.db
        db_path = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
        if not db_path:
            db_path = str(Path(__file__).parent.parent / "data" / "anti_stalker.db")

        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """INSERT INTO bio_link_visits
                   (link_id, visitor_ip, user_agent, referer, visited_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (link_id, visitor_ip, user_agent, referer, datetime.utcnow().isoformat()),
            )
            conn.commit()
            logger.info(f"Visit stored synchronously for link_id={link_id}")
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Synchronous visit storage failed: {e}", exc_info=True)


async def _store_visit(
    link_id: str,
    visitor_ip: str,
    user_agent: str,
    referer: str,
) -> None:
    """Store a BioLinkVisit record in the database.

    Includes error handling for geolocation failures so that the visit
    is still recorded even if IP lookup fails.

    Args:
        link_id: The tracking link code.
        visitor_ip: Visitor's IP address.
        user_agent: Visitor's User-Agent string.
        referer: Visitor's referer URL.
    """
    from core.database import get_session
    from core.models import BioLinkVisit

    # Attempt geolocation but do not let it block visit storage
    country = None
    city = None
    try:
        from trapnet.geolocator import GeoLocator
        geolocator = GeoLocator()
        location = await asyncio.wait_for(
            geolocator.locate_ip(visitor_ip), timeout=10.0
        )
        country = location.get("country")
        city = location.get("city")
    except asyncio.TimeoutError:
        logger.warning(f"Geolocation timed out for IP {visitor_ip}")
    except Exception as e:
        logger.warning(f"Geolocation failed for IP {visitor_ip}: {e}")

    try:
        async for session in get_session():
            visit = BioLinkVisit(
                link_id=link_id,
                visitor_ip=visitor_ip,
                user_agent=user_agent,
                referer=referer,
                country=country,
                city=city,
                visited_at=datetime.utcnow(),
            )
            session.add(visit)
            await session.commit()
            logger.info(
                f"Visit stored: link_id={link_id}, ip={visitor_ip}, "
                f"country={country}, city={city}"
            )
    except Exception as e:
        logger.error(
            f"Database error storing visit for link_id={link_id}: {e}",
            exc_info=True,
        )
        # Fallback to synchronous storage
        _store_visit_sync(link_id, visitor_ip, user_agent, referer)


def _update_fingerprint_async(
    link_id: str,
    visitor_ip: str,
    device_info: dict,
) -> None:
    """Update a BioLinkVisit record with fingerprint data asynchronously.

    Uses asyncio.run_coroutine_threadsafe to schedule work on the main
    event loop from the Flask thread. Falls back to synchronous update
    if the async bridge is unavailable.

    Args:
        link_id: The tracking link code.
        visitor_ip: Visitor's IP address.
        device_info: Fingerprint data collected by JavaScript.
    """
    with _main_loop_lock:
        loop = _main_loop

    if loop is not None and loop.is_running():
        future = asyncio.run_coroutine_threadsafe(
            _update_fingerprint(link_id, visitor_ip, device_info),
            loop,
        )
        future.add_done_callback(_log_future_exception)
    else:
        logger.warning(
            "Main event loop not available; using sync fallback for fingerprint %s",
            link_id,
        )
        _update_fingerprint_sync(link_id, visitor_ip, device_info)


def _update_fingerprint_sync(
    link_id: str,
    visitor_ip: str,
    device_info: dict,
) -> None:
    """Synchronous fallback for updating fingerprint data via sqlite3.

    Args:
        link_id: The tracking link code.
        visitor_ip: Visitor's IP address.
        device_info: Fingerprint data to store.
    """
    import json

    try:
        settings = get_settings()
        db_url = settings.database_url
        db_path = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
        if not db_path:
            db_path = str(Path(__file__).parent.parent / "data" / "anti_stalker.db")

        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """UPDATE bio_link_visits SET device_info = ?
                   WHERE link_id = ? AND visitor_ip = ?
                   ORDER BY visited_at DESC LIMIT 1""",
                (json.dumps(device_info), link_id, visitor_ip),
            )
            conn.commit()
            logger.info(f"Fingerprint updated synchronously for link_id={link_id}")
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Synchronous fingerprint update failed: {e}", exc_info=True)


async def _update_fingerprint(
    link_id: str,
    visitor_ip: str,
    device_info: dict,
) -> None:
    """Update the most recent BioLinkVisit record with fingerprint data.

    Finds the matching visit record by link_id and IP, then updates
    the device_info JSON field.

    Args:
        link_id: The tracking link code.
        visitor_ip: Visitor's IP address.
        device_info: Fingerprint data to store.
    """
    try:
        from sqlalchemy import select, desc
        from core.database import get_session
        from core.models import BioLinkVisit

        async for session in get_session():
            result = await session.execute(
                select(BioLinkVisit)
                .where(
                    BioLinkVisit.link_id == link_id,
                    BioLinkVisit.visitor_ip == visitor_ip,
                )
                .order_by(desc(BioLinkVisit.visited_at))
                .limit(1)
            )
            visit = result.scalar_one_or_none()
            if visit:
                visit.device_info = device_info
                await session.commit()
                logger.info(f"Fingerprint updated for link_id={link_id}")
            else:
                logger.warning(
                    f"No visit record found for fingerprint update: "
                    f"link_id={link_id}, ip={visitor_ip}"
                )
    except Exception as e:
        logger.error(
            f"Error updating fingerprint for link_id={link_id}: {e}",
            exc_info=True,
        )
