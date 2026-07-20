"""Production settings — a real public key is mandatory."""

import os

from .base import *  # noqa: F401,F403

DEBUG = False

if not (os.environ.get("SMARTHR_JWT_PUBLIC_KEY") or os.environ.get("SMARTHR_JWT_PUBLIC_KEY_FILE")):
    raise RuntimeError(
        "smarthr360-core-hr production requires SMARTHR_JWT_PUBLIC_KEY(_FILE) "
        "to verify tokens issued by smarthr360-auth."
    )

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# --- Security headers (added in Phase 4 hardening) -------------------------
# Behind the TLS-terminating reverse proxy (see deploy/local-https), trust the
# forwarded scheme and enforce HSTS / anti-framing / no-sniff.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
