import asyncio
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.database import AsyncSessionLocal
from app.models import Conversation, Message, Product, Promotion, Prompt, FAQ, Setting, Ticket
from app.services import ai_engine, instagram, vision
from app.services.redis_client import get_redis
from app.services.telegram import send_order_ticket
from app.logging_config import get_logger

logger = get_logger(__name__)

PENDING_TICKET_KEY = "pending_ticket:{conversation_id}"


async def _get_offline_message(db: AsyncSession) -> str | None:
    """Returns the offline message if outside working hours, None if within hours."""
    result = await db.execute(
        select(Setting).where(
            Setting.key.in_(["is_24_7", "working_hours_start", "working_hours_end", "offline_message", "timezone"])
        )
    )
    settings_map = {s.key: s.value for s in result.scalars().all()}

    if settings_map.get("is_24_7", "true").lower() == "true":
        return None

    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        tz_name = settings_map.get("timezone", "Asia/Tashkent")
        try:
            tz = ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, KeyError):
            tz = ZoneInfo("Asia/Tashkent")
        now_local = datetime.now(tz)
    except ImportError:
        now_local = datetime.now(timezone.utc)

    current_time = now_local.strftime("%H:%M")
    start = settings_map.get("working_hours_start", "09:00")
    end = settings_map.get("working_hours_end", "22:00")

    if start <= current_time <= end:
        return None

    return settings_map.get(
        "offline_message",
        "Hozir ish soatlaridan tashqaridamiz. Tez orada javob beramiz.",
    )


async def _get_or_create_conversation(
    db: AsyncSession,
    instagram_user_id: str,
    instagram_username: str | None,
    source: str,
) -> Conversation:
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.instagram_user_id == instagram_user_id,
            Conversation.status == "active",
        )
        .order_by(Conversation.started_at.desc())
        .limit(1)
    )
    conv = result.scalar_one_or_none()
    if conv:
        return conv

    conv = Conversation(
        instagram_user_id=instagram_user_id,
        instagram_username=instagram_username,
        source=source,
        status="active",
        funnel_stage="greeting",
    )
    db.add(conv)
    await db.flush()
    return conv


async def _load_context(db: AsyncSession) -> dict:
    """Load products, active promotions, prompts, and FAQ from DB."""
    products_result = await db.execute(
        select(Product).where(Product.is_available == True)
    )
    products = [
        {"name": p.name, "description": p.description, "price": p.price}
        for p in products_result.scalars().all()
    ]

    today = datetime.now(timezone.utc).date()
    promotions_result = await db.execute(
        select(Promotion).where(
            Promotion.is_active == True,
            Promotion.start_date <= today,
            Promotion.end_date >= today,
        )
    )
    promotions = [
        {
            "name": p.name,
            "type": p.type,
            "value": p.value,
            "description_for_bot": p.description_for_bot,
            "promo_code": p.promo_code,
            "is_active": p.is_active,
            "start_date": p.start_date,
            "end_date": p.end_date,
        }
        for p in promotions_result.scalars().all()
    ]

    prompts_result = await db.execute(select(Prompt))
    prompts = {p.type: p.content for p in prompts_result.scalars().all()}

    faq_result = await db.execute(select(FAQ).order_by(FAQ.sort_order))
    faq_items = [
        {"question": f.question, "answer": f.answer}
        for f in faq_result.scalars().all()
    ]

    return {
        "products": products,
        "promotions": promotions,
        "prompts": prompts,
        "faq_items": faq_items,
    }


async def _get_conversation_history(
    db: AsyncSession, conversation_id
) -> list[dict]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(20)
    )
    messages = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in messages]


async def _get_payment_card_info(db: AsyncSession) -> str:
    result = await db.execute(
        select(Setting).where(
            Setting.key.in_(["payment_card_number", "payment_card_owner", "payment_bank"])
        )
    )
    settings_map = {s.key: s.value for s in result.scalars().all()}
    card_num = settings_map.get("payment_card_number", "")
    card_owner = settings_map.get("payment_card_owner", "")
    bank = settings_map.get("payment_bank", "")
    return f"Karta: {card_num} | Egasi: {card_owner} | Bank: {bank}"


async def _update_pending_ticket(redis, conversation_id: str, extracted_data: dict):
    key = PENDING_TICKET_KEY.format(conversation_id=conversation_id)
    existing_raw = await redis.get(key)
    existing = json.loads(existing_raw) if existing_raw else {}
    # Only overwrite with non-null values
    for field, value in extracted_data.items():
        if value is not None:
            existing[field] = value
    await redis.set(key, json.dumps(existing), ex=86400 * 7)
    return existing


async def _create_ticket_from_pending(
    db: AsyncSession,
    redis,
    conversation: Conversation,
    payment_method: str,
    payment_status: str,
    payment_screenshot_url: str | None,
    payment_transaction_id: str | None,
    payment_amount_verified: int | None,
    notes: str | None = None,
) -> Ticket:
    key = PENDING_TICKET_KEY.format(conversation_id=str(conversation.id))
    raw = await redis.get(key)
    data = json.loads(raw) if raw else {}

    ticket = Ticket(
        client_instagram=conversation.instagram_username or conversation.instagram_user_id,
        client_name=data.get("client_name"),
        client_phone=data.get("client_phone"),
        client_city=data.get("client_city"),
        client_address=data.get("client_address"),
        product_name=data.get("product_name", "Unknown"),
        product_quantity=data.get("product_quantity") or 1,
        total_amount=data.get("total_amount") or 0,
        payment_method=payment_method,
        payment_status=payment_status,
        payment_screenshot_url=payment_screenshot_url,
        payment_transaction_id=payment_transaction_id,
        payment_amount_verified=payment_amount_verified,
        notes=notes,
    )
    db.add(ticket)
    await db.flush()

    # Link ticket to conversation
    conversation.ticket_id = ticket.id
    conversation.status = "converted"
    conversation.ended_at = datetime.now(timezone.utc)

    await redis.delete(key)
    return ticket


async def _handle_dm_async(
    instagram_user_id: str,
    instagram_username: str | None,
    message_text: str,
    media_url: str | None,
    source: str = "dm",
):
    redis = await get_redis()

    async with AsyncSessionLocal() as db:
        # Check working hours first
        offline_msg = await _get_offline_message(db)
        if offline_msg:
            logger.info("outside_working_hours", instagram_user_id=instagram_user_id)
            await db.commit()
            try:
                await instagram.send_dm(instagram_user_id, offline_msg)
            except Exception as exc:
                logger.error("instagram_send_failed", error=str(exc))
            return

        conv = await _get_or_create_conversation(
            db, instagram_user_id, instagram_username, source
        )

        if conv.status == "converted":
            logger.info("conversation_already_converted", conv_id=str(conv.id))
            return

        # Persist client message
        client_msg = Message(
            conversation_id=conv.id,
            role="client",
            content=message_text,
            media_url=media_url,
        )
        db.add(client_msg)

        context = await _load_context(db)
        history = await _get_conversation_history(db, conv.id)

        system_prompt = context["prompts"].get("system", "You are a helpful sales assistant.")
        sales_script = context["prompts"].get(conv.funnel_stage, "")
        has_image = bool(media_url)

        # Vision module: if in payment stage and image sent
        vision_result = None
        bot_reply_hint = None
        payment_status = "pending"
        payment_transaction_id = None
        payment_amount_verified = None

        if conv.funnel_stage == "payment" and has_image:
            try:
                img_bytes = await instagram.download_media(media_url)
                pending_raw = await redis.get(
                    PENDING_TICKET_KEY.format(conversation_id=str(conv.id))
                )
                pending_data = json.loads(pending_raw) if pending_raw else {}
                expected_amount = pending_data.get("total_amount", 0)

                vision_result = await vision.analyze_payment_screenshot(img_bytes, expected_amount)
                payment_status, bot_reply_hint = vision.determine_payment_action(vision_result)
                payment_transaction_id = vision_result.get("transaction_id")
                payment_amount_verified = vision_result.get("amount")
            except Exception as exc:
                logger.error("vision_module_failed", error=str(exc))
                bot_reply_hint = "request_resend"

        # AI Sales Engine
        bot_reply = None
        ai_result = None
        try:
            ai_result = await ai_engine.generate_sales_response(
                system_prompt=system_prompt,
                products=context["products"],
                promotions=context["promotions"],
                sales_script=sales_script,
                faq_items=context["faq_items"],
                history=history,
                current_message=message_text,
                current_message_has_image=has_image,
                payment_hint=bot_reply_hint,
            )
            bot_reply = ai_result["reply"]

            # Save old stage before updating so the card-info check is correct
            old_stage = conv.funnel_stage
            new_stage = ai_result.get("funnel_stage", conv.funnel_stage)
            if new_stage in ai_engine.VALID_FUNNEL_STAGES:
                conv.funnel_stage = new_stage

            # Append card info the first time we enter the payment stage
            if new_stage == "payment" and old_stage != "payment":
                card_info = await _get_payment_card_info(db)
                bot_reply = f"{bot_reply}\n\n{card_info}"

            # Update pending ticket data
            extracted = ai_result.get("extracted_data", {})
            if any(v is not None for v in extracted.values()):
                await _update_pending_ticket(redis, str(conv.id), extracted)

            # Handle completed stage
            if new_stage == "completed" and conv.status != "converted":
                payment_method = "transfer" if has_image else "cash"
                ticket = await _create_ticket_from_pending(
                    db=db,
                    redis=redis,
                    conversation=conv,
                    payment_method=payment_method,
                    payment_status=payment_status,
                    payment_screenshot_url=media_url,
                    payment_transaction_id=payment_transaction_id,
                    payment_amount_verified=payment_amount_verified,
                    notes=f"Vision confidence: {vision_result.get('confidence')}" if vision_result else None,
                )
                await db.commit()
                # Send ticket to Telegram (outside transaction)
                try:
                    await send_order_ticket(ticket)
                except Exception as exc:
                    logger.error("telegram_ticket_send_failed", error=str(exc))

        except Exception as exc:
            logger.error("ai_engine_failed", error=str(exc), exc_info=True)
            bot_reply = ai_engine.FALLBACK_MESSAGE_UZ

        # Persist bot reply
        bot_msg = Message(
            conversation_id=conv.id,
            role="bot",
            content=bot_reply,
        )
        db.add(bot_msg)

        # Update message count
        conv.message_count = (conv.message_count or 0) + 2

        await db.commit()

    # Send reply via Instagram (outside transaction)
    try:
        count = await instagram.increment_daily_message_count(redis)
        if count > settings_module.ig_daily_message_limit:
            logger.error("instagram_daily_limit_exceeded", count=count)
            return
        await instagram.send_dm(instagram_user_id, bot_reply)
    except Exception as exc:
        logger.error("instagram_send_failed", error=str(exc))


# Import settings here to avoid circular at module level
from app.config import settings as settings_module


@celery_app.task(name="app.tasks.message_processing.process_dm", bind=True, max_retries=2)
def process_dm(
    self,
    instagram_user_id: str,
    instagram_username: str | None,
    message_text: str,
    media_url: str | None,
    source: str = "dm",
):
    try:
        asyncio.run(
            _handle_dm_async(
                instagram_user_id=instagram_user_id,
                instagram_username=instagram_username,
                message_text=message_text,
                media_url=media_url,
                source=source,
            )
        )
    except Exception as exc:
        logger.error("process_dm_task_failed", error=str(exc), exc_info=True)
        raise self.retry(exc=exc, countdown=5)
