import asyncio
import json
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, update, exists, and_, not_
from sqlalchemy.exc import IntegrityError
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
    # First check for active conversation
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

    # Check for recently converted conversation (within 7 days) — client may want to update order
    cutoff = datetime.utcnow() - timedelta(days=7)
    result2 = await db.execute(
        select(Conversation)
        .where(
            Conversation.instagram_user_id == instagram_user_id,
            Conversation.status == "converted",
            Conversation.started_at >= cutoff,
        )
        .order_by(Conversation.started_at.desc())
        .limit(1)
    )
    recent_converted = result2.scalar_one_or_none()
    if recent_converted:
        return recent_converted

    conv = Conversation(
        instagram_user_id=instagram_user_id,
        instagram_username=instagram_username,
        source=source,
        status="active",
        funnel_stage="greeting",
    )
    db.add(conv)
    try:
        await db.flush()
    except IntegrityError:
        # Another concurrent task already created the active conversation
        # (unique partial index violation). Roll back and fetch the existing one.
        await db.rollback()
        result2 = await db.execute(
            select(Conversation)
            .where(
                Conversation.instagram_user_id == instagram_user_id,
                Conversation.status == "active",
            )
            .order_by(Conversation.started_at.desc())
            .limit(1)
        )
        conv = result2.scalar_one_or_none()
        if conv is None:
            raise RuntimeError(
                f"Could not create or find active conversation for {instagram_user_id}"
            )
    return conv


async def _load_context(db: AsyncSession) -> dict:
    """Load products, active promotions, prompts, and FAQ from DB."""
    products_result = await db.execute(
        select(Product).where(Product.is_available == True)
    )
    products = [
        {"name": p.name, "description": p.description, "price": p.price, "image_url": p.image_url}
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

    tg_link_result = await db.execute(
        select(Setting.value).where(Setting.key == "telegram_group_link")
    )
    telegram_group_link = tg_link_result.scalar_one_or_none() or None

    return {
        "products": products,
        "promotions": promotions,
        "prompts": prompts,
        "faq_items": faq_items,
        "telegram_group_link": telegram_group_link,
    }


async def _get_conversation_history(
    db: AsyncSession, conversation_id
) -> list[dict]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(10)
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


SUSPICIOUS_WORDS = [
    # Uzbek offensive/fraud
    "ot", "essa", "blyad", "xaromi", "harom", "jinni", "ahmoq", "tentak", "yot",
    "stupid", "idiot", "blyat", "suka", "pizda", "ebal", "nahuy", "huesos",
    # Russian offensive
    "блять", "сука", "пизда", "хуй", "ебал", "нахуй", "блядь",
]

FRAUD_PATTERNS = [
    "to'lov qildim", "tolov qildim", "pul yubordim", "pul jo'natdim",
    "transfer qildim", "to'lab bo'ldim", "tolab boldim",
]

# Phrases attempting to manipulate the price to 0 or get products for free
PRICE_MANIPULATION_PATTERNS = [
    # Uzbek Latin — free/0-price requests
    "tekinga ber", "tekin ber", "bepul ber", "tekinga bera", "tekin bera",
    "tekinga ol", "tekin ol", "bepul ol", "bepulga ber", "bepulga ol",
    "tekinga", "bepulga", "bepul qil",
    "0 ga ber", "0ga ber", "0 somga", "0somga", "nol somga", "nol ga ber",
    "0 sum", "0 so'm", "nol so'm",
    # Uzbek Latin — price reduction
    "narxini tushir", "narxni tushir", "arzon qil", "arzonroq qil",
    "yarim narx", "yarim narxda", "chegirma ber", "chegirma qil",
    "narxini kamaytir", "narxni kamaytir", "kam narxda ber",
    "arzonga ber", "arzonroq ber", "ucuz ber",
    # Uzbek Latin — refusal to pay
    "haq tolamayman", "tolamayman", "pul bermayman", "pulni qaytaring",
    "aldadingiz", "firibgar", "sotib olmayman lekin",
    # Uzbek Cyrillic — free requests
    "текин", "бепул", "текинга", "текин бер", "бепул бер",
    "текинга бер", "текинга ол",
    # Russian Cyrillic — free requests
    "бесплатно", "даром", "за 0", "за ноль", "нол сум",
    "скидку дай", "сделай дешевле", "бесплатно дай", "даром дай",
    "ман учун текин", "мен учун текин",
]

# Patterns that indicate a prompt injection attempt (fake system/admin notes in user message)
PROMPT_INJECTION_PATTERNS = [
    "[system", "[admin", "[override", "[maintenance", "[instruction", "[note:",
    "<system", "<admin", "<override",
    "system note", "maintenance mode", "price_matrix", "override price",
    "discount coupon", "free2026", "coupon_code", "promo_code",
    "administrator applied", "admin applied", "system directive", "technical maintenance",
    "do not prompt user for payment", "output confirmation message",
    "системная директива", "системное сообщение", "технический режим",
    "скидочный купон", "применен администратором",
]


def _detect_prompt_injection(text: str) -> bool:
    """Return True if the message contains fake system/admin instruction injection."""
    text_lower = text.lower()
    return any(pat in text_lower for pat in PROMPT_INJECTION_PATTERNS)


import re as _re

def _strip_injection_blocks(text: str) -> str:
    """Remove [SYSTEM NOTE: ...] and similar blocks from user text before sending to AI."""
    # Remove [SYSTEM...] style blocks
    cleaned = _re.sub(
        r'\[(?:SYSTEM|ADMIN|OVERRIDE|MAINTENANCE|INSTRUCTION|NOTE)[^\]]*\]',
        '[REMOVED]', text, flags=_re.IGNORECASE | _re.DOTALL,
    )
    # Remove <SYSTEM>...</SYSTEM> style blocks
    cleaned = _re.sub(
        r'<(?:SYSTEM|ADMIN|OVERRIDE)[^>]*>.*?</(?:SYSTEM|ADMIN|OVERRIDE)>',
        '[REMOVED]', cleaned, flags=_re.IGNORECASE | _re.DOTALL,
    )
    return cleaned.strip()


async def _send_fraud_alert(conv, reason: str) -> None:
    """Send fraud/suspicious activity alert to Telegram operator group."""
    from app.services.telegram import send_admin_alert
    username = conv.instagram_username or conv.instagram_user_id
    msg = (
        f"🚨 SHUBHALI FAOLIYAT\n\n"
        f"👤 Instagram: @{username}\n"
        f"💬 Sabab: {reason}\n"
        f"🔗 Suhbat ID: {str(conv.id)[:8]}..."
    )
    try:
        await send_admin_alert(msg)
    except Exception as exc:
        logger.error("fraud_alert_send_failed", error=str(exc))


def _check_suspicious(text: str) -> tuple[bool, str]:
    """Returns (is_suspicious, reason). Checks offensive words and fraud patterns."""
    text_lower = text.lower()
    for word in SUSPICIOUS_WORDS:
        if word in text_lower:
            return True, f"Haqoratli so'z: '{word}'"
    for pattern in FRAUD_PATTERNS:
        if pattern in text_lower:
            return True, f"To'lovsiz tasdiqlashga urinish: '{pattern}'"
    return False, ""


def _check_price_manipulation(text: str) -> tuple[bool, str]:
    """Returns (is_manipulation, matched_pattern) if client is trying to get a free/discounted product."""
    text_lower = text.lower()
    for pattern in PRICE_MANIPULATION_PATTERNS:
        if pattern in text_lower:
            return True, pattern
    return False, ""


PAYMENT_INTENT_KEYWORDS = [
    "tolov", "to'lov", "to'lamoqchi", "tolamoqchi", "tolay", "to'lay",
    "pul yubor", "transfer", "to'lash", "tolash",
    "payment", "pay", "chek yuboraman", "screenshot",
    "karta raqam", "pul yuboray", "to'lab",
    # Cyrillic
    "оплатить", "оплата", "перевести", "скриншот чека",
]

# Keywords that indicate client will pay CASH on delivery (no screenshot expected)
CASH_PAYMENT_KEYWORDS = [
    # Uzbek Latin — cash/naqd variants
    "naqd", "naxt", "naqt", "nakd", "naqd pul", "naxt pul",
    # Uzbek Latin — delivery/courier
    "yetkazib beruvchi", "yetkazuvchi", "kuryer", "kurer", "kurер",
    "dastavka", "dastafka", "dastavkachi", "dostavka", "dastafkachi",
    "yetkazib", "yetkazuvchiga", "yetkazib beruvchiga",
    # Uzbek Latin — "when I receive/get it"
    "qo'lma-qol", "qolma qol", "olganda", "olganida", "olganimda",
    "qabul qilganda", "qabul qilganida", "topshirganda", "topshirganida",
    "kelganda", "yetib kelganda",
    "olganda to'lay", "olganda beraman", "olganda to'layman",
    "cash", "pochta",
    # Uzbek Cyrillic — cash
    "нақд", "нақт", "накд", "нақд пул",
    # Uzbek Cyrillic — courier/delivery (the most common cash phrases in Cyrillic Uzbek)
    "курерга", "куrerга", "курерга", "курьерга",
    "курер", "курьер",
    "етказиб", "етказувчи", "юборувчига",
    "олганда", "олганимда", "қабул", "топширганда",
    "қўлма-қўл", "қўлда",
    # Russian — cash/delivery
    "нал", "наличными", "наличка", "нал оплата",
    "курьер наличными", "при доставке", "при получении",
    "наложенным",
]


def _is_payment_intent(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in PAYMENT_INTENT_KEYWORDS)


def _is_cash_payment(text: str) -> bool:
    """Return True if client is clearly confirming cash-on-delivery payment."""
    t = text.lower()
    return any(kw in t for kw in CASH_PAYMENT_KEYWORDS)


async def _restore_payment_context(
    db: AsyncSession, redis, conv: Conversation
) -> bool:
    """
    For a converted conversation with an unpaid ticket: restore Redis pending
    data from the ticket and reactivate the conversation at payment stage.
    Returns True if successfully restored so the caller can fall through to
    the normal payment flow.
    """
    from app.models import Ticket as TicketModel
    from sqlalchemy import select as _select

    if not conv.ticket_id:
        return False

    result = await db.execute(_select(TicketModel).where(TicketModel.id == conv.ticket_id))
    ticket = result.scalar_one_or_none()

    if not ticket or ticket.payment_status == "confirmed":
        return False  # already paid or not found

    # Rebuild Redis pending data from the existing ticket
    pending_data = {
        k: v for k, v in {
            "client_name": ticket.client_name,
            "client_phone": ticket.client_phone,
            "client_city": ticket.client_city,
            "client_address": ticket.client_address,
            "product_name": ticket.product_name,
            "product_quantity": ticket.product_quantity,
            "total_amount": ticket.total_amount,
            "_payment_stage_entered": True,
            "_existing_ticket_id": str(ticket.id),
        }.items() if v is not None
    }

    key = PENDING_TICKET_KEY.format(conversation_id=str(conv.id))
    await redis.set(key, json.dumps(pending_data), ex=86400 * 7)

    # Reactivate conversation at payment stage
    conv.status = "active"
    conv.funnel_stage = "payment"
    return True


def _build_receipt_fingerprint(vision_result: dict) -> str | None:
    """
    Build a stable fingerprint for a payment receipt to detect reuse.
    Uses transaction_id if available; falls back to amount+date+card combination.
    Returns None if there's not enough info to fingerprint reliably.
    """
    import hashlib

    txn_id = (vision_result.get("transaction_id") or "").strip()
    amount = vision_result.get("amount") or 0
    date = (vision_result.get("date") or "").strip()
    card = (vision_result.get("sender_card_last4") or "").strip()

    if txn_id:
        # Transaction ID is globally unique — best fingerprint
        return f"txn:{txn_id}"

    # Fallback: hash of amount + date + card (if we have at least 2 of 3)
    fields_present = sum(1 for f in [amount, date, card] if f)
    if fields_present >= 2:
        raw = f"{amount}:{date}:{card}"
        return "hash:" + hashlib.sha256(raw.encode()).hexdigest()[:16]

    return None


async def _register_receipt(redis, vision_result: dict, owner_label: str) -> None:
    """Store a confirmed receipt fingerprint in Redis for 180 days."""
    fp = _build_receipt_fingerprint(vision_result)
    if fp:
        await redis.set(f"used_receipt:{fp}", owner_label, ex=86400 * 180)


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

    existing_ticket_id = data.get("_existing_ticket_id")

    # If this is a returning payer for an EXISTING ticket — update it, don't create a new one
    if existing_ticket_id:
        from sqlalchemy import select as _sel
        result = await db.execute(_sel(Ticket).where(Ticket.id == existing_ticket_id))
        ticket = result.scalar_one_or_none()
        if ticket:
            ticket.payment_method = payment_method
            ticket.payment_status = payment_status
            if payment_screenshot_url:
                ticket.payment_screenshot_url = payment_screenshot_url
            if payment_transaction_id:
                ticket.payment_transaction_id = payment_transaction_id
            if payment_amount_verified:
                ticket.payment_amount_verified = payment_amount_verified
            ticket.updated_at = datetime.now(timezone.utc)
            if notes:
                ticket.notes = (ticket.notes or "") + f"\n{notes}"
            conversation.status = "converted"
            conversation.ended_at = datetime.utcnow()
            await redis.delete(key)
            return ticket

    # New ticket
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

    conversation.ticket_id = ticket.id
    conversation.status = "converted"
    conversation.ended_at = datetime.utcnow()

    await redis.delete(key)
    return ticket


async def _get_owner_greeting(db: AsyncSession, redis, instagram_user_id: str) -> str | None:
    """
    Return the owner-configured first-DM greeting message if:
      - 'dm_greeting_message' setting is set (non-empty), AND
      - the user did NOT arrive via a comment auto-DM (so we don't double-greet).
    Returns None if the AI should generate the greeting instead.
    """
    # If this user got a comment auto-DM, skip the greeting — they already heard from us
    comment_welcomed = await redis.exists(f"comment_welcomed:{instagram_user_id}")
    if comment_welcomed:
        return None

    result = await db.execute(
        select(Setting.value).where(Setting.key == "dm_greeting_message")
    )
    greeting = result.scalar_one_or_none() or ""
    return greeting.strip() or None


UPDATE_KEYWORDS = [
    "manzil", "adres", "address", "raqam", "telefon", "phone", "number",
    "ism", "isim", "name", "o'zgartir", "ozgartir", "yangilash", "yangilamoq",
    "xato", "noto'g'ri", "notogri", "esdan", "change", "update", "correct",
]

# Words that signal new-order intent (must appear together with order words below)
_NEW_SIGNAL_WORDS = [
    "yangi", "yana", "qaytadan", "yangidan", "yana bir", "new", "reorder",
    "опять", "снова", "новый", "повторно",
]
_ORDER_WORDS = [
    "buyurtma", "zakaz", "order", "заказ", "olmoqchi", "sotib", "olmоqchiman",
    "bermoqchi", "xohlayman", "xohlaydigan",
]


def _is_new_order_intent(text: str) -> bool:
    """Return True if the message clearly expresses intent to place a NEW order."""
    t = text.lower()
    has_new_signal = any(w in t for w in _NEW_SIGNAL_WORDS)
    has_order_word = any(w in t for w in _ORDER_WORDS)
    return has_new_signal and has_order_word


async def _handle_converted_conversation(
    db: AsyncSession,
    redis,
    conv: Conversation,
    instagram_user_id: str,
    message_text: str,
    media_url: str | None = None,
) -> None:
    """Handle messages in already-converted (ordered) conversations.
    Saves client + bot messages to DB so the dashboard counts them correctly."""
    from sqlalchemy import select
    from app.models import Ticket

    # Always persist the client message so dashboard counts this conversation
    db.add(Message(conversation_id=conv.id, role="client", content=message_text, media_url=media_url))

    text_lower = message_text.lower()
    is_update_request = any(kw in text_lower for kw in UPDATE_KEYWORDS)

    if not is_update_request:
        reply = (
            "✅ Buyurtmangiz qabul qilingan va jarayonda!\n\n"
            "📝 Manzil, ism yoki telefon o'zgartirish uchun yangi ma'lumotni yozing.\n"
            "🛍 Yangi buyurtma berish uchun: \"Yangi buyurtma bermoqchiman\" deb yozing."
        )
        db.add(Message(conversation_id=conv.id, role="bot", content=reply))
        conv.message_count = (conv.message_count or 0) + 2
        await db.commit()
        try:
            await instagram.send_dm(instagram_user_id, reply)
        except Exception as exc:
            logger.error("instagram_send_failed", error=str(exc))
        return

    # Find the linked ticket
    ticket = None
    if conv.ticket_id:
        result = await db.execute(select(Ticket).where(Ticket.id == conv.ticket_id))
        ticket = result.scalar_one_or_none()

    if not ticket:
        reply = "✅ Buyurtmangiz topilmadi. Iltimos operator bilan bog'laning."
        db.add(Message(conversation_id=conv.id, role="bot", content=reply))
        conv.message_count = (conv.message_count or 0) + 2
        await db.commit()
        try:
            await instagram.send_dm(instagram_user_id, reply)
        except Exception as exc:
            logger.error("instagram_send_failed", error=str(exc))
        return

    # Use AI to extract the new data from the message
    update_prompt = f"""The customer wants to update their order details. Extract updated info from their message.
Customer message: "{message_text}"
Current order: name={ticket.client_name}, phone={ticket.client_phone}, city={ticket.client_city}, address={ticket.client_address}

Respond ONLY with valid JSON:
{{"client_name": null, "client_phone": null, "client_city": null, "client_address": null}}
Only include fields the customer is explicitly changing. Use null for unchanged fields."""

    updated_fields = {}
    try:
        import google.generativeai as genai
        from app.config import settings as _settings
        genai.configure(api_key=_settings.gemini_api_key)
        model = genai.GenerativeModel(_settings.gemini_model)
        resp = await asyncio.to_thread(model.generate_content, update_prompt)
        import re, json as _json
        raw = resp.text.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw)
        extracted = _json.loads(raw)
        updated_fields = {k: v for k, v in extracted.items() if v is not None}
    except Exception as exc:
        logger.error("order_update_ai_failed", error=str(exc))

    if not updated_fields:
        reply = (
            "Yangilash uchun quyidagilarni yozing:\n"
            "• Yangi manzil\n• Yangi telefon raqam\n• Yangi ism"
        )
        db.add(Message(conversation_id=conv.id, role="bot", content=reply))
        conv.message_count = (conv.message_count or 0) + 2
        await db.commit()
        try:
            await instagram.send_dm(instagram_user_id, reply)
        except Exception:
            pass
        return

    # Apply updates to ticket
    for field, value in updated_fields.items():
        if hasattr(ticket, field):
            setattr(ticket, field, value)
    ticket.updated_at = datetime.now(timezone.utc)

    # Notify Telegram
    from app.services.telegram import edit_ticket_message, send_admin_alert
    changes_text = "\n".join(f"• {k.replace('client_', '').capitalize()}: {v}" for k, v in updated_fields.items())

    # Confirm to client
    changes_readable = "\n".join(f"✅ {k.replace('client_', '').capitalize()}: {v}" for k, v in updated_fields.items())
    reply = (
        f"✅ Buyurtmangiz ma'lumotlari yangilandi!\n\n"
        f"{changes_readable}\n\n"
        f"Agar boshqa o'zgarishlar bo'lsa — yozing 😊"
    )
    db.add(Message(conversation_id=conv.id, role="bot", content=reply))
    conv.message_count = (conv.message_count or 0) + 2
    await db.commit()
    await db.refresh(ticket)

    await send_admin_alert(
        f"📝 BUYURTMA YANGILANDI\n\n"
        f"👤 @{conv.instagram_username or conv.instagram_user_id}\n"
        f"🎫 #{ticket.ticket_number:05d}\n\n"
        f"Yangi ma'lumotlar:\n{changes_text}"
    )
    if ticket.telegram_message_id:
        try:
            await edit_ticket_message(ticket.telegram_message_id, ticket)
        except Exception:
            pass

    try:
        await instagram.send_dm(instagram_user_id, reply)
    except Exception as exc:
        logger.error("instagram_send_failed", error=str(exc))


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

        # Resolve username if webhook didn't provide it (fallback inside the task)
        if not instagram_username:
            try:
                profile = await instagram.get_user_profile(instagram_user_id)
                instagram_username = profile.get("username") or profile.get("name") or None
            except Exception:
                pass

        conv = await _get_or_create_conversation(
            db, instagram_user_id, instagram_username, source
        )

        # Backfill username on existing conversation if it was missing
        if instagram_username and not conv.instagram_username:
            conv.instagram_username = instagram_username

        if conv.status == "converted":
            if _is_new_order_intent(message_text):
                # Client wants a NEW order — open a fresh active conversation
                logger.info("new_order_intent_detected", conv_id=str(conv.id), user=instagram_user_id)
                conv = Conversation(
                    instagram_user_id=instagram_user_id,
                    instagram_username=instagram_username,
                    source=source,
                    status="active",
                    funnel_stage="greeting",
                )
                db.add(conv)
                await db.flush()
                # Fall through to normal AI processing below
            elif has_image or _is_payment_intent(message_text):
                # Client returning to pay for their existing unpaid order
                restored = await _restore_payment_context(db, redis, conv)
                if restored:
                    logger.info("payment_context_restored", conv_id=str(conv.id), user=instagram_user_id)
                    # Fall through to normal payment flow — conv is now active at payment stage
                else:
                    # Ticket already paid or not found — fall through to normal update handler
                    await _handle_converted_conversation(db, redis, conv, instagram_user_id, message_text, media_url)
                    return
            else:
                # Client wants to update existing order details
                await _handle_converted_conversation(db, redis, conv, instagram_user_id, message_text, media_url)
                return

        is_first_message = conv.message_count == 0

        # Persist client message
        client_msg = Message(
            conversation_id=conv.id,
            role="client",
            content=message_text,
            media_url=media_url,
        )
        db.add(client_msg)

        # Prompt injection detection — strip fake [SYSTEM NOTE] blocks from the message
        # and alert operators; continue processing with the cleaned text
        if _detect_prompt_injection(message_text):
            logger.warning("prompt_injection_detected", conv_id=str(conv.id), preview=message_text[:200])
            await _send_fraud_alert(
                conv,
                f"🚨 PROMPT INJECTION URINISHI!\n"
                f"Mijoz soxta 'tizim buyrug'i' yubordi:\n{message_text[:300]}"
            )
            message_text = _strip_injection_blocks(message_text)

        # Price manipulation detection — block immediately, do not call AI
        is_price_manip, manip_pattern = _check_price_manipulation(message_text)
        if is_price_manip:
            logger.warning("price_manipulation_attempt", conv_id=str(conv.id), pattern=manip_pattern)
            await _send_fraud_alert(
                conv,
                f"💰 NARX MANIPULYATSIYASI: Mijoz mahsulotni tekin yoki 0 narxda olishga urindi!\n"
                f"Pattern: '{manip_pattern}'"
            )
            refusal = (
                "Kechirasiz, mahsulotlar faqat belgilangan narxda sotiladi. "
                "Narxni o'zgartirish yoki tekin berish imkoni yo'q 🙏\n\n"
                "Agar savollaringiz bo'lsa, boshqa narsa so'rang 😊"
            )
            # client_msg already added above — only add the bot reply
            db.add(Message(conversation_id=conv.id, role="bot", content=refusal))
            conv.message_count = (conv.message_count or 0) + 2
            await db.commit()
            try:
                await instagram.send_dm(instagram_user_id, refusal)
            except Exception as exc:
                logger.error("instagram_send_failed", error=str(exc))
            return

        # Suspicious content detection — alert operators but still process normally
        is_suspicious, suspicious_reason = _check_suspicious(message_text)
        if is_suspicious:
            logger.warning("suspicious_content_detected", conv_id=str(conv.id), reason=suspicious_reason)
            await _send_fraud_alert(conv, suspicious_reason)

        context = await _load_context(db)
        history = await _get_conversation_history(db, conv.id)

        system_prompt = context["prompts"].get("system", "You are a helpful sales assistant.")
        sales_script = context["prompts"].get(conv.funnel_stage, "")

        # Fetch current pending order so AI never forgets what was collected
        _pending_raw = await redis.get(PENDING_TICKET_KEY.format(conversation_id=str(conv.id)))
        _pending_for_ai = json.loads(_pending_raw) if _pending_raw else {}
        pending_order_summary: str | None = None
        _order_fields = {
            "product_name": "Mahsulot",
            "product_quantity": "Miqdor",
            "total_amount": "Narx",
            "client_name": "Ism",
            "client_phone": "Telefon",
            "client_city": "Shahar",
            "client_address": "Manzil",
        }
        _order_lines = [
            f"{label}: {_pending_for_ai[key]}"
            for key, label in _order_fields.items()
            if _pending_for_ai.get(key) is not None
        ]
        if _order_lines:
            pending_order_summary = "\n".join(_order_lines)
        has_image = bool(media_url)

        # Vision module: if in payment stage and image sent
        vision_result = None
        bot_reply_hint = None
        payment_status = "pending"
        payment_transaction_id = None
        payment_amount_verified = None
        product_image_url: str | None = None
        reused_receipt = False  # must be initialised here — vision block may be skipped for cash orders

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

                # ── Duplicate/old receipt detection ───────────────────────────
                reused_receipt = False
                txn_fingerprint = _build_receipt_fingerprint(vision_result)
                if txn_fingerprint:
                    used_key = f"used_receipt:{txn_fingerprint}"
                    already_used = await redis.get(used_key)
                    if already_used:
                        existing_owner = already_used.decode() if isinstance(already_used, bytes) else already_used
                        reused_receipt = True
                        logger.warning(
                            "duplicate_receipt_detected",
                            fingerprint=txn_fingerprint,
                            conv_id=str(conv.id),
                            original_user=existing_owner,
                        )
                        await _send_fraud_alert(
                            conv,
                            f"⚠️ ESKI/TAKRORIY CHEK yuborildi!\n"
                            f"TXN: {payment_transaction_id or 'noma lum'}\n"
                            f"Summa: {payment_amount_verified:,} UZS\n"
                            f"Avval ishlatgan: {existing_owner}"
                        )
                        bot_reply_hint = "duplicate_receipt"
                        payment_status = "pending"

                # ── Amount mismatch alert ─────────────────────────────────────
                if not reused_receipt and not vision_result.get("amount_matches") and vision_result.get("amount"):
                    detected_amount = vision_result.get("amount", 0)
                    await _send_fraud_alert(
                        conv,
                        f"To'lov summasi mos kelmadi! "
                        f"Kutilgan: {expected_amount:,} UZS, "
                        f"Chekda: {detected_amount:,} UZS. "
                        f"TXN: {payment_transaction_id or 'noma lum'}"
                    )

                # ── Recipient card mismatch check ─────────────────────────────
                # Verify screenshot's recipient card matches OUR card
                recipient_last4 = (vision_result.get("recipient_card_last4") or "").strip()
                if recipient_last4 and not reused_receipt:
                    card_result = await db.execute(
                        select(Setting.value).where(Setting.key == "payment_card_number")
                    )
                    our_card_num = (card_result.scalar_one_or_none() or "").replace(" ", "").replace("-", "")
                    our_last4 = our_card_num[-4:] if len(our_card_num) >= 4 else ""
                    if our_last4 and recipient_last4 != our_last4:
                        logger.warning(
                            "wrong_recipient_card",
                            screenshot_card=recipient_last4,
                            our_card=our_last4,
                            conv_id=str(conv.id),
                        )
                        await _send_fraud_alert(
                            conv,
                            f"🚨 NOTO'G'RI KARTAGA O'TKAZMA!\n"
                            f"Chekdagi oluvchi karta: **{recipient_last4}\n"
                            f"Bizning karta oxirgi 4: {our_last4}\n"
                            f"Ehtimol boshqa kartaga pul o'tkazilgan!"
                        )
                        bot_reply_hint = "request_resend"
                        payment_status = "pending"

            except Exception as exc:
                logger.error("vision_module_failed", error=str(exc))
                bot_reply_hint = "request_resend"

        # ── Greeting shortcut ─────────────────────────────────────────────────
        # On the very first message of a new conversation, use the owner-configured
        # greeting text (if set) instead of calling the AI.  This saves an API call
        # and gives the owner full control over the opening line.
        bot_reply = None
        owner_greeting = None
        if is_first_message:
            owner_greeting = await _get_owner_greeting(db, redis, instagram_user_id)

        if owner_greeting:
            bot_reply = owner_greeting
            # Funnel stage stays at "greeting" — AI takes over from message 2 onwards
            logger.info("using_owner_greeting", instagram_user_id=instagram_user_id)
        else:
            # ── AI Sales Engine ───────────────────────────────────────────────
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
                    telegram_group_link=context.get("telegram_group_link"),
                    pending_order_summary=pending_order_summary,
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
                    # Mark that this conversation entered payment stage (for fraud detection)
                    await _update_pending_ticket(redis, str(conv.id), {"_payment_stage_entered": True})

                # Update pending ticket data
                extracted = ai_result.get("extracted_data", {})
                # Guard: reject AI-extracted total_amount of 0 — price manipulation defense
                extracted_amount = extracted.get("total_amount")
                if extracted_amount is not None and int(extracted_amount) <= 0:
                    logger.warning(
                        "ai_zero_price_rejected",
                        conv_id=str(conv.id),
                        extracted_amount=extracted_amount,
                    )
                    extracted["total_amount"] = None
                if any(v is not None for v in extracted.values()):
                    await _update_pending_ticket(redis, str(conv.id), extracted)

                # Check if a product image should be sent
                if new_stage in ("presentation", "closing", "qualification"):
                    mentioned_product = extracted.get("product_name")
                    for p in context["products"]:
                        name_match = (
                            (mentioned_product and mentioned_product.lower() in p["name"].lower())
                            or p["name"].lower() in bot_reply.lower()
                        )
                        if name_match and p.get("image_url"):
                            product_image_url = p["image_url"]
                            break

                # Handle completed stage — ONLY if payment is actually confirmed or cash order
                if new_stage == "completed" and conv.status != "converted":
                    # Anti-fraud: if funnel passed through payment stage, require a verified screenshot.
                    # If the client never sent an image (just text-claimed payment), block completion.
                    pending_raw = await redis.get(PENDING_TICKET_KEY.format(conversation_id=str(conv.id)))
                    pending_data = json.loads(pending_raw) if pending_raw else {}
                    payment_was_in_flow = pending_data.get("_payment_stage_entered", False)

                    # Cash detection: keyword match on current message OR AI extracted payment_method
                    is_cash_order = (
                        _is_cash_payment(message_text)
                        or pending_data.get("payment_method") == "cash"
                    )
                    if payment_was_in_flow and not has_image and payment_status != "confirmed" and not is_cash_order:
                        # Someone tried to text-claim payment without sending a screenshot
                        logger.warning("fraud_attempt_text_payment_claim", conv_id=str(conv.id))
                        await _send_fraud_alert(conv, "Mijoz to'lov qilmay 'to'lov qildim' deb so'z bilan buyurtmani tasdiqlashga urindi!")
                        bot_reply = (
                            "⚠️ To'lov uchun iltimos chek rasmini yuboring! "
                            "Faqat rasmli chek qabul qilinadi 📸"
                        )
                        conv.funnel_stage = "payment"
                    elif reused_receipt:
                        # Duplicate/old receipt — block order creation
                        logger.warning("duplicate_receipt_blocked_order", conv_id=str(conv.id))
                        bot_reply = (
                            "❌ Bu chek avval ishlatilgan yoki eskirgan!\n\n"
                            "Iltimos yangi to'lov chekini yuboring. "
                            "Har bir buyurtma uchun alohida to'lov talab etiladi 📸"
                        )
                        conv.funnel_stage = "payment"
                    elif not pending_data.get("total_amount") or int(pending_data.get("total_amount") or 0) <= 0:
                        # Hard block: never create a 0-price or missing-price order
                        logger.warning("zero_price_order_blocked", conv_id=str(conv.id), pending=pending_data)
                        await _send_fraud_alert(
                            conv,
                            "⚠️ 0 narxli yoki noaniq narxli buyurtma yaratishga urinish bloklandi!\n"
                            f"Pending data: {pending_data}"
                        )
                        bot_reply = (
                            "Buyurtmani yakunlash uchun avval mahsulot va narxini tasdiqlashimiz kerak.\n\n"
                            "Qaysi mahsulotni olmoqchisiz va narxi qancha ekanligini tasdiqlang 🛍"
                        )
                        conv.funnel_stage = "closing"
                    else:
                        # Use AI-detected payment_method if available, else infer from image
                        payment_method = (
                            pending_data.get("payment_method")
                            or ("transfer" if has_image else "cash")
                        )
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
                        # Register receipt fingerprint so it can't be reused
                        if vision_result:
                            owner_label = conv.instagram_username or conv.instagram_user_id
                            await _register_receipt(redis, vision_result, owner_label)
                        # Send ticket to Telegram (outside transaction)
                        try:
                            await send_order_ticket(ticket)
                        except Exception as exc:
                            logger.error("telegram_ticket_send_failed", error=str(exc))

            except Exception as exc:
                logger.error("ai_engine_failed", error=str(exc), exc_info=True)
                bot_reply = ai_engine.FALLBACK_MESSAGE_UZ

        # Safety net: never persist or send None / empty string
        if not bot_reply:
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

    # Send product image if bot mentioned a product by name and that product has an image
    if product_image_url:
        try:
            await instagram.send_dm_image(instagram_user_id, product_image_url)
            logger.info("product_image_sent", user=instagram_user_id)
        except Exception as exc:
            logger.debug("product_image_send_failed", error=str(exc))


# Import settings here to avoid circular at module level
from app.config import settings as settings_module

STALE_HOURS = 24  # conversations idle longer than this are auto-closed


async def _close_stale_conversations_async() -> int:
    """
    Mark active conversations idle for STALE_HOURS hours as 'ended'.

    Uses a single bulk UPDATE with two sub-conditions (no N+1):
      1. Has messages, but the most recent one is older than the cutoff.
      2. Has NO messages and started_at is older than the cutoff.
    """
    from datetime import timedelta
    from sqlalchemy import func as sqlfunc

    # Use naive UTC datetimes — the DB column is TIMESTAMP WITHOUT TIME ZONE
    from datetime import datetime as _dt
    cutoff = _dt.utcnow() - timedelta(hours=STALE_HOURS)
    now_utc = _dt.utcnow()

    # Subquery: latest message timestamp per conversation
    latest_msg_sq = (
        select(sqlfunc.max(Message.created_at))
        .where(Message.conversation_id == Conversation.id)
        .correlate(Conversation)
        .scalar_subquery()
    )

    # Subquery: does any message exist for this conversation?
    has_msg_sq = (
        select(Message.id)
        .where(Message.conversation_id == Conversation.id)
        .correlate(Conversation)
        .exists()
    )

    stmt = (
        update(Conversation)
        .where(
            Conversation.status == "active",
            # Either: has messages, all older than cutoff
            # Or: no messages at all and conversation itself is old
            (
                and_(has_msg_sq, latest_msg_sq < cutoff)
                | and_(not_(has_msg_sq), Conversation.started_at < cutoff)
            ),
        )
        .values(status="ended", ended_at=now_utc)
        .execution_options(synchronize_session="fetch")
    )

    async with AsyncSessionLocal() as db:
        result = await db.execute(stmt)
        closed = result.rowcount
        if closed:
            await db.commit()
            logger.info("stale_conversations_closed", count=closed)

    return closed


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


@celery_app.task(name="app.tasks.message_processing.close_stale_conversations")
def close_stale_conversations():
    """Periodic Beat task: auto-close conversations idle for STALE_HOURS hours."""
    try:
        closed = asyncio.run(_close_stale_conversations_async())
        return {"closed": closed}
    except Exception as exc:
        logger.error("close_stale_conversations_failed", error=str(exc), exc_info=True)
        return {"closed": 0, "error": str(exc)}


def _get_smart_comment_reply(template: str, sender_name: str) -> str:
    """Return a smart comment reply based on template.
    If template contains {name}, fill it; keep it as-is otherwise."""
    name_part = f" {sender_name}," if sender_name else ""
    if "{name}" in template:
        return template.replace("{name}", sender_name) if sender_name else template.replace("{name}", "").strip()
    return template


async def _process_comment_dm_async(
    sender_id: str,
    sender_name: str | None,
    comment_id: str | None = None,
):
    """
    When a user comments on a post:
      1. Post a public reply under their comment (if comment_reply_message is set).
      2. Send them a DM (if comment_auto_dm_message is set).

    Both actions are independent — a failure in one does not block the other.
    """
    redis = await get_redis()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Setting).where(
                Setting.key.in_([
                    "comment_auto_dm_enabled",
                    "comment_auto_dm_message",
                    "comment_reply_message",
                ])
            )
        )
        settings_map = {s.key: s.value for s in result.scalars().all()}

    comment_auto_dm_enabled = settings_map.get("comment_auto_dm_enabled", "true").lower() == "true"

    display_name = (sender_name or "").strip()

    def _fill(template: str) -> str:
        return template.replace("{name}", display_name) if display_name else template.replace("{name}", "")

    # ── 1. Public comment reply ───────────────────────────────────────────────
    reply_template = settings_map.get("comment_reply_message", "").strip()
    if reply_template and comment_id:
        # Dedup: only post one public reply per comment even if the task is retried
        reply_dedup_key = f"comment_reply_sent:{comment_id}"
        already_replied = await redis.exists(reply_dedup_key)
        if not already_replied:
            try:
                smart_reply = _get_smart_comment_reply(reply_template, display_name)
                new_reply_id = await instagram.reply_to_comment(comment_id, smart_reply)
                await redis.set(reply_dedup_key, "1", ex=86400)
                # ── KEY FIX: mark the bot's own reply comment so the webhook
                # handler skips it and doesn't trigger another reply loop.
                # We use the actual comment ID returned by the API — this is
                # reliable regardless of how Instagram represents the account ID.
                if new_reply_id:
                    await redis.set(f"our_comment:{new_reply_id}", "1", ex=86400)
                    logger.info("comment_public_reply_sent", comment_id=comment_id, reply_id=new_reply_id)
                else:
                    logger.info("comment_public_reply_sent", comment_id=comment_id)
            except Exception as exc:
                logger.error("comment_public_reply_failed", comment_id=comment_id, error=str(exc))
        else:
            logger.debug("comment_public_reply_skipped_dedup", comment_id=comment_id)

    # ── 2. DM ─────────────────────────────────────────────────────────────────
    if not comment_auto_dm_enabled:
        logger.info("comment_auto_dm_disabled_post_reply")
        return

    dm_template = settings_map.get("comment_auto_dm_message", "").strip()
    if not dm_template:
        logger.warning(
            "comment_auto_dm_message_empty — DM not sent. "
            "Set 'comment_auto_dm_message' in Settings to enable DMs to commenters."
        )
        return

    # Dedup: only DM each person once per 24 hours from comments
    dm_dedup_key = f"comment_dm_sent:{sender_id}"
    already_dmed = await redis.exists(dm_dedup_key)
    if already_dmed:
        logger.info("comment_dm_skipped_already_sent_today", sender_id=sender_id)
        return

    try:
        count = await instagram.increment_daily_message_count(redis)
        if count > settings_module.ig_daily_message_limit:
            logger.error("instagram_daily_limit_exceeded_comment_dm", count=count)
            return

        logger.info("comment_dm_attempting", sender_id=sender_id, sender_name=sender_name)
        await instagram.send_dm(sender_id, _fill(dm_template))
        await redis.set(dm_dedup_key, "1", ex=86400)
        await redis.set(f"comment_welcomed:{sender_id}", "1", ex=86400)
        logger.info("comment_auto_dm_sent", sender_id=sender_id)
    except Exception as exc:
        logger.error(
            "comment_dm_send_failed",
            sender_id=sender_id,
            sender_name=sender_name,
            error=str(exc),
            hint=(
                "If error is 'not reachable' or 200 with error code 10, "
                "the user must message the business first (standard API access). "
                "Advanced Access is required to initiate DMs to commenters."
            ),
        )
        raise  # Let Celery retry handle it


@celery_app.task(
    name="app.tasks.message_processing.process_comment_dm",
    bind=True,
    max_retries=2,
)
def process_comment_dm(
    self,
    sender_id: str,
    sender_name: str | None = None,
    comment_id: str | None = None,
):
    """Celery task: public comment reply + auto-DM for Instagram comment events."""
    try:
        asyncio.run(
            _process_comment_dm_async(
                sender_id=sender_id,
                sender_name=sender_name,
                comment_id=comment_id,
            )
        )
    except Exception as exc:
        logger.error("process_comment_dm_failed", sender_id=sender_id, error=str(exc), exc_info=True)
        raise self.retry(exc=exc, countdown=10)


# ─────────────────────────────────────────────────────────────────────────────
# Comment polling fallback
# Meta does NOT send `comments` webhook events in Development Mode.
# This Beat task polls recent posts every 5 minutes and processes new comments,
# giving the same behaviour as the webhook once the app is live.
# ─────────────────────────────────────────────────────────────────────────────

async def _poll_comments_async() -> int:
    """
    Fetch comments on recent posts and trigger process_comment_dm for any
    that haven't been processed yet (dedup via Redis key comment_dm_sent:<uid>:<post_id>).
    """
    import httpx
    from datetime import datetime as _dt

    redis = await get_redis()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Setting).where(
                Setting.key.in_([
                    "instagram_access_token",
                    "instagram_page_id",
                    "comment_auto_dm_enabled",
                ])
            )
        )
        smap = {s.key: s.value for s in result.scalars().all()}

    if smap.get("comment_auto_dm_enabled", "true").lower() != "true":
        return 0

    access_token = smap.get("instagram_access_token", "").strip()
    page_id = smap.get("instagram_page_id", "").strip()
    if not access_token or not page_id:
        logger.warning("comment_poll_skipped_no_credentials")
        return 0

    base = settings_module.meta_graph_api_url
    queued = 0

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            # Resolve ALL known IDs for this account so we can skip its own comments.
            # The same account can appear with different IDs depending on API context
            # (e.g. scoped user ID vs. Instagram Business Account ID in comment threads).
            me_resp = await client.get(
                f"{base}/me",
                params={"fields": "id,username", "access_token": access_token},
            )
            me_data = me_resp.json() if me_resp.status_code == 200 else {}
            page_ig_user_id = me_data.get("id")
            page_ig_username = (me_data.get("username") or "").lower()
            # Build a set of all own-account IDs to skip (includes both the /me scoped ID
            # and the instagram_page_id setting which may differ in comment thread context)
            own_ids = {id_ for id_ in [page_ig_user_id, page_id] if id_}

            # Fetch recent posts (last 10)
            media_resp = await client.get(
                f"{base}/{page_id}/media",
                params={"fields": "id,timestamp", "limit": "10", "access_token": access_token},
            )
            if media_resp.status_code != 200:
                logger.error("comment_poll_media_failed", status=media_resp.status_code, body=media_resp.text[:200])
                return 0

            posts = media_resp.json().get("data", [])
            # Process all posts — dedup keys prevent double-sending
            for post in posts:
                post_id = post.get("id")

                # Fetch comments on this post
                comments_resp = await client.get(
                    f"{base}/{post_id}/comments",
                    params={"fields": "id,from,timestamp", "limit": "50", "access_token": access_token},
                )
                if comments_resp.status_code != 200:
                    continue

                for comment in comments_resp.json().get("data", []):
                    sender_id = comment.get("from", {}).get("id")
                    sender_name = comment.get("from", {}).get("username")
                    comment_id = comment.get("id")
                    if not sender_id or not comment_id:
                        continue

                    # Skip the page's own comments (can't DM yourself).
                    # Check by ID and also by username — the account may appear with
                    # different IDs in /me vs. comment thread contexts.
                    sender_username_lower = (sender_name or "").lower()
                    if sender_id in own_ids or (page_ig_username and sender_username_lower == page_ig_username):
                        logger.debug("comment_poll_skip_own_comment", sender_id=sender_id, sender_name=sender_name)
                        continue

                    # Skip if this specific comment was already replied to
                    # Using comment_id (globally unique) prevents webhook + polling collision
                    comment_seen_key = f"comment_id_processed:{comment_id}"
                    if await redis.exists(comment_seen_key):
                        continue
                    # Mark this comment as processed immediately (before queuing)
                    await redis.set(comment_seen_key, "1", ex=86400)

                    process_comment_dm.delay(
                        sender_id=sender_id,
                        sender_name=sender_name,
                        comment_id=comment_id,
                    )
                    queued += 1
                    logger.info("comment_poll_queued", sender_id=sender_id, comment_id=comment_id)

    except Exception as exc:
        logger.error("comment_poll_failed", error=str(exc))

    if queued:
        logger.info("comment_poll_complete", queued=queued)
    return queued


@celery_app.task(name="app.tasks.message_processing.poll_new_comments")
def poll_new_comments():
    """Beat task: poll Instagram posts for new comments every 5 min (dev mode fallback)."""
    try:
        queued = asyncio.run(_poll_comments_async())
        return {"queued": queued}
    except Exception as exc:
        logger.error("poll_new_comments_failed", error=str(exc), exc_info=True)
        return {"queued": 0, "error": str(exc)}
