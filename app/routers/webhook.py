import hashlib
import hmac

from fastapi import APIRouter, Request, Response, HTTPException, Query
from app.config import settings
from app.services.instagram import verify_webhook_signature
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.get("/instagram")
async def webhook_verify(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
):
    """Meta webhook verification endpoint."""
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        logger.info("webhook_verified")
        return Response(content=hub_challenge, media_type="text/plain")
    logger.warning("webhook_verification_failed", mode=hub_mode)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/instagram")
async def webhook_receive(request: Request):
    """Receive Instagram webhook events (DMs and comments)."""
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not verify_webhook_signature(payload, signature):
        logger.warning("webhook_invalid_signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    logger.info(
        "webhook_event_received",
        object_type=data.get("object"),
        raw_payload=str(data)[:500],   # full debug — remove once stable
    )

    # Process each entry
    for entry in data.get("entry", []):
        entry_keys = list(entry.keys())
        logger.info("webhook_entry_keys", keys=entry_keys)

        # DM events
        for messaging in entry.get("messaging", []):
            await _handle_messaging_event(messaging)

        # Comment / feed events
        for change in entry.get("changes", []):
            field = change.get("field")
            logger.info("webhook_change_field", field=field, value_keys=list(change.get("value", {}).keys()))
            if field in ("comments", "feed"):
                await _handle_comment_event(change.get("value", {}))

    # Always return 200 quickly — Meta will retry if we don't
    return {"status": "ok"}


async def _handle_messaging_event(messaging: dict):
    """Parse and enqueue a DM event."""
    from app.tasks.message_processing import process_dm
    from app.services.redis_client import get_redis

    sender = messaging.get("sender", {})
    message = messaging.get("message", {})

    sender_id = sender.get("id")
    if not sender_id:
        return

    # Skip echo events — when the bot sends a DM, Instagram echoes it back
    # with is_echo=true or with a recipient matching the sender pattern.
    if message.get("is_echo"):
        logger.info("dm_echo_skipped", sender_id=sender_id)
        return

    # Deduplicate using the Instagram message ID (mid) — Meta can deliver duplicates
    mid = message.get("mid")
    if mid:
        redis = await get_redis()
        dedup_key = f"dm_mid:{mid}"
        if await redis.exists(dedup_key):
            logger.info("dm_duplicate_skipped", mid=mid)
            return
        await redis.set(dedup_key, "1", ex=3600)

    message_text = message.get("text", "")
    media_url = None

    attachments = message.get("attachments", [])
    if attachments:
        # Prefer the first image attachment
        for att in attachments:
            if att.get("type") in ("image", "file"):
                media_url = att.get("payload", {}).get("url")
                break
        if not message_text:
            message_text = "[image]"

    if not message_text and not media_url:
        return

    logger.info("dm_event", sender_id=sender_id, has_media=bool(media_url))

    process_dm.delay(
        instagram_user_id=sender_id,
        instagram_username=None,
        message_text=message_text,
        media_url=media_url,
        source="dm",
    )


async def _handle_comment_event(value: dict):
    """
    Auto-DM every commenter with the owner-configured greeting template.

    No Gemini classification — all comments trigger the DM (deduped per user/post).
    The owner controls the message text via the 'comment_auto_dm_message' setting.
    """
    from app.services.redis_client import get_redis
    from app.tasks.message_processing import process_comment_dm

    sender_id = value.get("from", {}).get("id")
    # Meta sends "username" in comment events (not "name")
    sender_name = value.get("from", {}).get("name") or value.get("from", {}).get("username")
    post_id = value.get("post_id") or value.get("media_id") or value.get("parent_id", "")
    comment_id = value.get("id")  # comment ID for public reply

    logger.info(
        "comment_event_parsed",
        sender_id=sender_id,
        sender_name=sender_name,
        comment_id=comment_id,
        post_id=post_id,
        value_preview=str(value)[:200],
    )

    if not sender_id:
        return

    redis = await get_redis()

    # Dedup: send at most one auto-DM per user per post per day
    dedup_key = f"comment_dm_sent:{sender_id}:{post_id}"
    if await redis.exists(dedup_key):
        logger.info("comment_dm_skipped_dedup", sender_id=sender_id)
        return

    # Skip if this user already has an active conversation with us
    from app.database import AsyncSessionLocal
    from app.models import Conversation
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Conversation).where(
                Conversation.instagram_user_id == sender_id,
                Conversation.status == "active",
            ).limit(1)
        )
        if result.scalar_one_or_none():
            logger.info("comment_dm_skipped_active_conv", sender_id=sender_id)
            return

    # Mark dedup NOW (before task runs) so concurrent webhook deliveries don't double-send
    await redis.set(dedup_key, "1", ex=86400)

    logger.info("comment_dm_queued", sender_id=sender_id, sender_name=sender_name)

    # Offload to Celery — keeps the webhook response fast
    process_comment_dm.delay(
        sender_id=sender_id,
        sender_name=sender_name,
        comment_id=comment_id,
    )
