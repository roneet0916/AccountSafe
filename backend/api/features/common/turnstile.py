# api/features/common/turnstile.py
"""
Cloudflare Turnstile verification utilities.
"""

import logging
import os
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def get_turnstile_secret_key():
    """Read key dynamically to ensure .env is loaded."""
    return os.getenv("TURNSTILE_SECRET_KEY", "")


TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile_token(token: str, remote_ip: str = None) -> dict:
    """
    Verify Cloudflare Turnstile token.

    Args:
        token: The Turnstile token from the frontend
        remote_ip: Optional IP address of the user

    Returns:
        dict with 'success' boolean and optional 'error-codes' list
    """
    if not token:
        logger.warning("Turnstile verification called without a token")
        return {"success": False, "error-codes": ["missing-token"]}

    secret = get_turnstile_secret_key()
    if not secret:
        logger.error("TURNSTILE_SECRET_KEY is not set on the backend")
        return {"success": False, "error-codes": ["missing-secret"]}

    payload = {"secret": secret, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        response = requests.post(TURNSTILE_VERIFY_URL, data=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        if not result.get("success"):
            # Surface the actual Cloudflare reason in server logs so operators
            # can tell "invalid-input-secret" (misconfigured key) apart from
            # "timeout-or-duplicate" (user re-submitted a stale token).
            logger.warning(
                "Turnstile verification failed: error-codes=%s messages=%s",
                result.get("error-codes"),
                result.get("messages"),
            )
        return result
    except requests.exceptions.RequestException as e:
        logger.exception("Turnstile verification request failed: %s", e)
        return {"success": False, "error-codes": ["verification-failed"], "error_message": str(e)}


def get_client_ip(request) -> str:
    """
    Get the client's IP address from the request.
    Handles proxy headers like X-Forwarded-For.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip
