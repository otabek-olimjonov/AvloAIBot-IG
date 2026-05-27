import hashlib
import hmac
import asyncio
from datetime import date

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

GRAPH_API_BASE = settings.meta_graph_api_url


def verify_webhook_signature(payload: bytes, signature_header: str | None) -> bool:
    """Verify X-Hub-Signature-256 header from Meta."""
    if settings.skip_webhook_signature:
        logger.warning("webhook_signature_check_skipped")
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        logger.warning("webhook_sig_missing_or_bad_prefix", header=signature_header)
        return False
    expected_sig = signature_header[len("sha256="):]
    computed_sig = hmac.new(  # noqa: S324
        settings.meta_app_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    match = hmac.compare_digest(computed_sig, expected_sig)
    if not match:
        logger.warning(
            "webhook_sig_mismatch",
            expected=expected_sig,
            computed=computed_sig,
            secret_prefix=settings.meta_app_secret[:6] + "...",
            payload_len=len(payload),
            payload_preview=payload[:120].decode("utf-8", errors="replace"),
        )
    return match


@retry(
    retry=retry_if_exception_type(httpx.HTTPStatusError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
async def _get_access_token() -> str:
    """Read access token from DB settings, fall back to env var."""
    try:
        from app.database import AsyncSessionLocal
        from app.models import Setting
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Setting.value).where(Setting.key == "instagram_access_token")
            )
            token = result.scalar_one_or_none()
            if token and token.strip():
                return token.strip()
    except Exception:
        pass
    return settings.meta_access_token


async def send_dm(recipient_igsid: str, message_text: str) -> dict:
    """Send a DM to an Instagram user via the Graph API."""
    url = f"{GRAPH_API_BASE}/me/messages"
    payload = {
        "recipient": {"id": recipient_igsid},
        "message": {"text": message_text},
        "messaging_type": "RESPONSE",
    }
    access_token = await _get_access_token()
    params = {"access_token": access_token}

    async with httpx.AsyncClient(timeout=30.0) as client:
        start = asyncio.get_event_loop().time()
        response = await client.post(url, json=payload, params=params)
        elapsed = asyncio.get_event_loop().time() - start

        logger.info(
            "instagram_send_dm",
            recipient=recipient_igsid,
            status_code=response.status_code,
            elapsed_ms=round(elapsed * 1000),
        )

        if response.status_code == 429:
            logger.warning("instagram_rate_limited", response=response.text)
            response.raise_for_status()

        if response.status_code >= 400:
            logger.error(
                "instagram_send_dm_failed",
                status_code=response.status_code,
                body=response.text,
            )
            response.raise_for_status()

        return response.json()


async def reply_to_comment(comment_id: str, message_text: str) -> dict:
    """Post a public reply to an Instagram comment."""
    access_token = await _get_access_token()
    url = f"{GRAPH_API_BASE}/{comment_id}/replies"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url,
            params={"access_token": access_token},
            json={"message": message_text},
        )
        logger.info(
            "instagram_comment_reply",
            comment_id=comment_id,
            status_code=response.status_code,
        )
        if response.status_code >= 400:
            logger.error(
                "instagram_comment_reply_failed",
                status_code=response.status_code,
                body=response.text,
            )
            response.raise_for_status()
        return response.json()


async def download_media(media_url: str) -> bytes:
    """Download an image from Instagram (requires access token)."""
    access_token = await _get_access_token()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            media_url,
            params={"access_token": access_token},
        )
        response.raise_for_status()
        return response.content


async def get_daily_message_count(redis_client) -> int:
    today = date.today().isoformat()
    key = f"ig_msg_count:{today}"
    count = await redis_client.get(key)
    return int(count) if count else 0


async def increment_daily_message_count(redis_client) -> int:
    today = date.today().isoformat()
    key = f"ig_msg_count:{today}"
    count = await redis_client.incr(key)
    # Expire at end of day (86400 seconds)
    await redis_client.expire(key, 86400)
    if count > settings.ig_daily_warning_threshold:
        logger.warning("instagram_daily_limit_approaching", count=count)
    return count
