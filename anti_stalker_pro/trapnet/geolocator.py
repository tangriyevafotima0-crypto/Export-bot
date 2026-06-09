"""IP geolocation module using geoip2 with fallback to ip-api.com.

Provides IP-to-location mapping for identifying where tracking link
visitors are located geographically.
"""

import asyncio
from typing import Optional

import aiohttp

from core.logger import get_logger

logger = get_logger(__name__)


class GeoLocator:
    """Locates IP addresses using geoip2 database or ip-api.com fallback.

    Attempts to use a local GeoIP2 database first for speed and privacy,
    then falls back to the free ip-api.com service if the database is
    unavailable.
    """

    def __init__(self) -> None:
        """Initialize the GeoLocator and attempt to load the GeoIP2 database."""
        self._geoip_reader: Optional[object] = None
        self._load_geoip_database()

    def _load_geoip_database(self) -> None:
        """Attempt to load a GeoIP2 database file.

        Looks for GeoLite2-City.mmdb in common locations.
        Silently continues if the database is not found.
        """
        try:
            import geoip2.database
            from pathlib import Path

            possible_paths = [
                Path(__file__).parent.parent / "data" / "GeoLite2-City.mmdb",
                Path("/usr/share/GeoIP/GeoLite2-City.mmdb"),
                Path("/var/lib/GeoIP/GeoLite2-City.mmdb"),
            ]

            for db_path in possible_paths:
                if db_path.exists():
                    self._geoip_reader = geoip2.database.Reader(str(db_path))
                    logger.info(f"GeoIP2 database loaded from {db_path}")
                    return

            logger.debug("GeoIP2 database not found, will use ip-api.com fallback")
        except ImportError:
            logger.debug("geoip2 package not available, using ip-api.com fallback")
        except Exception as e:
            logger.debug(f"Failed to load GeoIP2 database: {e}")

    async def locate_ip(self, ip_address: str) -> dict:
        """Locate an IP address, returning geographic information.

        Tries the local GeoIP2 database first, falls back to ip-api.com
        free API if the database is unavailable or the lookup fails.

        Args:
            ip_address: The IP address to look up.

        Returns:
            dict: Location data with keys: country, city, region,
                latitude, longitude. Values may be None if lookup fails.
        """
        if self._is_private_ip(ip_address):
            return {
                "country": "Private",
                "city": "Local Network",
                "region": None,
                "latitude": None,
                "longitude": None,
            }

        if self._geoip_reader:
            result = self._lookup_geoip2(ip_address)
            if result:
                return result

        return await self._lookup_ip_api(ip_address)

    def get_location_summary(self, ip_address: str) -> str:
        """Get a human-readable location summary for an IP address.

        Performs a synchronous lookup using the GeoIP2 database only
        (no network calls). For async lookups, use locate_ip().

        Args:
            ip_address: The IP address to look up.

        Returns:
            str: Human-readable location string (e.g., "Kyiv, Ukraine").
        """
        if self._is_private_ip(ip_address):
            return "Private/Local Network"

        if self._geoip_reader:
            result = self._lookup_geoip2(ip_address)
            if result:
                parts = []
                if result.get("city"):
                    parts.append(result["city"])
                if result.get("region"):
                    parts.append(result["region"])
                if result.get("country"):
                    parts.append(result["country"])
                return ", ".join(parts) if parts else "Unknown"

        return f"Unknown ({ip_address})"

    async def bulk_locate(self, ip_list: list[str]) -> list[dict]:
        """Batch process multiple IP addresses for geolocation.

        Processes each IP in the list and returns location data for all.
        Uses concurrent lookups for the ip-api.com fallback.

        Args:
            ip_list: List of IP addresses to locate.

        Returns:
            list[dict]: List of location dictionaries, one per IP,
                in the same order as the input list.
        """
        results = []
        for ip in ip_list:
            location = await self.locate_ip(ip)
            location["ip"] = ip
            results.append(location)
        return results

    def _lookup_geoip2(self, ip_address: str) -> Optional[dict]:
        """Look up an IP using the local GeoIP2 database.

        Args:
            ip_address: The IP address to look up.

        Returns:
            Optional[dict]: Location data or None if lookup fails.
        """
        try:
            response = self._geoip_reader.city(ip_address)
            return {
                "country": response.country.name,
                "city": response.city.name,
                "region": (
                    response.subdivisions.most_specific.name
                    if response.subdivisions
                    else None
                ),
                "latitude": response.location.latitude,
                "longitude": response.location.longitude,
            }
        except Exception as e:
            logger.debug(f"GeoIP2 lookup failed for {ip_address}: {e}")
            return None

    async def _lookup_ip_api(self, ip_address: str) -> dict:
        """Look up an IP using the free ip-api.com service.

        Makes an HTTP request to ip-api.com/json endpoint. Rate limited
        to 45 requests per minute on the free tier.

        Args:
            ip_address: The IP address to look up.

        Returns:
            dict: Location data with country, city, region, latitude,
                and longitude keys (values may be None on failure).
        """
        empty_result = {
            "country": None,
            "city": None,
            "region": None,
            "latitude": None,
            "longitude": None,
        }

        try:
            url = f"http://ip-api.com/json/{ip_address}?fields=status,country,city,regionName,lat,lon"
            async with aiohttp.ClientSession() as client_session:
                async with client_session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        return empty_result
                    data = await resp.json()

            if data.get("status") == "success":
                return {
                    "country": data.get("country"),
                    "city": data.get("city"),
                    "region": data.get("regionName"),
                    "latitude": data.get("lat"),
                    "longitude": data.get("lon"),
                }
            return empty_result

        except Exception as e:
            logger.debug(f"ip-api.com lookup failed for {ip_address}: {e}")
            return empty_result

    def _is_private_ip(self, ip_address: str) -> bool:
        """Check if an IP address is in a private/reserved range.

        Args:
            ip_address: The IP address to check.

        Returns:
            bool: True if the IP is private or reserved.
        """
        import ipaddress

        try:
            ip = ipaddress.ip_address(ip_address)
            return ip.is_private or ip.is_loopback or ip.is_reserved
        except ValueError:
            return False
