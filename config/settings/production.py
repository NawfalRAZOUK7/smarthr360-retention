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
