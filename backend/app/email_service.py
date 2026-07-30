"""Sends the OTP account-confirmation email via Resend's REST API.

No `resend` SDK dependency - it's a single POST, and `requests` is already
a dependency for Google's OAuth token verification. Falls back to logging
the OTP when RESEND_API_KEY is unset (see app/config.py) so registration
and verification stay testable with zero external accounts.
"""
import logging

import requests

from app.config import settings

log = logging.getLogger("email")

_RESEND_URL = "https://api.resend.com/emails"


def send_otp_email(to_email: str, otp_code: str) -> None:
    if not settings.resend_api_key:
        log.warning("RESEND_API_KEY not set - OTP for %s is: %s", to_email, otp_code)
        return

    try:
        response = requests.post(
            _RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": f"MeridianGrid <{settings.resend_from_email}>",
                "to": [to_email],
                "subject": "Confirm your MeridianGrid account",
                "html": (
                    f"<p>Your MeridianGrid confirmation code is:</p>"
                    f"<p style=\"font-size:28px;font-weight:700;letter-spacing:4px\">{otp_code}</p>"
                    f"<p>This code expires in {settings.otp_expire_minutes} minutes. "
                    f"If you didn't request this, you can ignore this email.</p>"
                ),
            },
            timeout=10,
        )
        if not response.ok:
            log.warning(
                "Resend rejected the OTP email for %s (%s %s) - the code was: %s",
                to_email, response.status_code, response.text, otp_code,
            )
    except requests.RequestException:
        log.warning("Failed to reach Resend for %s's OTP email - see server logs for the code: %s", to_email, otp_code)
