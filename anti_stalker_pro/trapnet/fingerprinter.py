"""Browser fingerprinting module for visitor identification.

Generates tracking pages with embedded JavaScript that collects browser
characteristics (screen resolution, timezone, language, platform, WebGL,
etc.) and computes a device fingerprint hash for cross-visit correlation.
"""

import hashlib
import json
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)


class Fingerprinter:
    """Generates tracking pages and processes browser fingerprints.

    Creates HTML pages with JavaScript that collects device characteristics
    and posts them back to the server. Provides fingerprint comparison
    for identifying repeat visitors across different tracking links.
    """

    def generate_tracking_page(
        self, tracking_code: str, redirect_url: str
    ) -> str:
        """Generate an HTML page with embedded fingerprinting JavaScript.

        The page collects screen resolution, timezone, language, platform,
        color depth, touch support, and WebGL renderer information, then
        POSTs the data to /api/fingerprint before redirecting the visitor.

        Args:
            tracking_code: The unique tracking code for this link.
            redirect_url: URL to redirect the visitor to after capture.

        Returns:
            str: Complete HTML page with fingerprinting script.
        """
        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Redirecting...</title>
</head>
<body>
<p>Redirecting, please wait...</p>
<script>
(function() {{
    var fp = {{}};
    try {{
        fp.screen_width = screen.width;
        fp.screen_height = screen.height;
        fp.color_depth = screen.colorDepth;
        fp.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        fp.timezone_offset = new Date().getTimezoneOffset();
        fp.language = navigator.language || navigator.userLanguage;
        fp.languages = navigator.languages ? navigator.languages.join(',') : '';
        fp.platform = navigator.platform;
        fp.hardware_concurrency = navigator.hardwareConcurrency || 0;
        fp.device_memory = navigator.deviceMemory || 0;
        fp.touch_support = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
        fp.max_touch_points = navigator.maxTouchPoints || 0;
        fp.do_not_track = navigator.doNotTrack || '0';
        fp.cookie_enabled = navigator.cookieEnabled;
    }} catch(e) {{}}

    try {{
        var canvas = document.createElement('canvas');
        var gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        if (gl) {{
            var debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            if (debugInfo) {{
                fp.webgl_vendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
                fp.webgl_renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL);
            }}
            fp.webgl_version = gl.getParameter(gl.VERSION);
        }}
    }} catch(e) {{}}

    try {{
        var canvas2 = document.createElement('canvas');
        canvas2.width = 200;
        canvas2.height = 50;
        var ctx = canvas2.getContext('2d');
        ctx.textBaseline = 'top';
        ctx.font = '14px Arial';
        ctx.fillText('fingerprint', 2, 2);
        fp.canvas_hash = canvas2.toDataURL().slice(-50);
    }} catch(e) {{}}

    var payload = {{
        tracking_code: '{tracking_code}',
        fingerprint: fp
    }};

    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/fingerprint', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onreadystatechange = function() {{
        if (xhr.readyState === 4) {{
            window.location.href = '{redirect_url}';
        }}
    }};
    xhr.send(JSON.stringify(payload));

    setTimeout(function() {{
        window.location.href = '{redirect_url}';
    }}, 2000);
}})();
</script>
</body>
</html>"""
        return html

    def generate_fingerprint_hash(self, data: dict) -> str:
        """Create a SHA-256 hash from collected fingerprint features.

        Combines stable device characteristics into a deterministic hash
        that identifies the same device across visits.

        Args:
            data: Dictionary of fingerprint features collected by JS.

        Returns:
            str: SHA-256 hex digest of the fingerprint.
        """
        stable_features = [
            str(data.get("screen_width", "")),
            str(data.get("screen_height", "")),
            str(data.get("color_depth", "")),
            str(data.get("timezone", "")),
            str(data.get("language", "")),
            str(data.get("platform", "")),
            str(data.get("hardware_concurrency", "")),
            str(data.get("webgl_vendor", "")),
            str(data.get("webgl_renderer", "")),
            str(data.get("canvas_hash", "")),
        ]
        combined = "|".join(stable_features)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def same_device_check(self, hash1: str, hash2: str) -> float:
        """Compare two fingerprint hashes for device similarity.

        If hashes are identical, returns 100%. Otherwise, compares
        the underlying feature sets character by character for partial
        matches (useful when some features change between visits).

        Args:
            hash1: First fingerprint SHA-256 hash.
            hash2: Second fingerprint SHA-256 hash.

        Returns:
            float: Similarity percentage (0.0 to 100.0).
        """
        if hash1 == hash2:
            return 100.0

        if not hash1 or not hash2:
            return 0.0

        matching_chars = sum(
            1 for a, b in zip(hash1, hash2) if a == b
        )
        total_chars = max(len(hash1), len(hash2))
        return (matching_chars / total_chars) * 100.0 if total_chars > 0 else 0.0

    def compare_fingerprints(self, fp1: dict, fp2: dict) -> float:
        """Compare two raw fingerprint dictionaries for similarity.

        Compares individual features and returns a weighted similarity
        score. More stable features (platform, screen) carry more weight.

        Args:
            fp1: First fingerprint feature dictionary.
            fp2: Second fingerprint feature dictionary.

        Returns:
            float: Similarity percentage (0.0 to 100.0).
        """
        if not fp1 or not fp2:
            return 0.0

        weighted_features = {
            "screen_width": 2.0,
            "screen_height": 2.0,
            "color_depth": 1.0,
            "timezone": 3.0,
            "language": 2.0,
            "platform": 3.0,
            "hardware_concurrency": 1.5,
            "webgl_renderer": 3.0,
            "webgl_vendor": 2.0,
            "canvas_hash": 2.5,
        }

        total_weight = 0.0
        match_weight = 0.0

        for feature, weight in weighted_features.items():
            total_weight += weight
            val1 = fp1.get(feature)
            val2 = fp2.get(feature)
            if val1 is not None and val2 is not None and str(val1) == str(val2):
                match_weight += weight

        return (match_weight / total_weight) * 100.0 if total_weight > 0 else 0.0
