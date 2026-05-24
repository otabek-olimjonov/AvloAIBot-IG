import asyncio
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message as TgMessage,
)
from aiogram.filters import Command

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

_bot: Bot | None = None
_dp: Dispatcher | None = None
_router = Router()


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=settings.telegram_bot_token)
    return _bot


def _build_ticket_keyboard(ticket_id: str, order_status: str) -> InlineKeyboardMarkup:
    if order_status == "new":
        buttons = [
            [InlineKeyboardButton(text="✋ Take order", callback_data=f"ticket:{ticket_id}:take")],
            [
                InlineKeyboardButton(text="✅ Completed", callback_data=f"ticket:{ticket_id}:complete"),
                InlineKeyboardButton(text="❌ Cancelled", callback_data=f"ticket:{ticket_id}:cancel"),
            ],
        ]
    elif order_status == "in_progress":
        buttons = [
            [
                InlineKeyboardButton(text="✅ Completed", callback_data=f"ticket:{ticket_id}:complete"),
                InlineKeyboardButton(text="❌ Cancelled", callback_data=f"ticket:{ticket_id}:cancel"),
            ],
        ]
    else:
        buttons = []
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _format_ticket_message(ticket) -> str:
    status_icon = "✅" if ticket.payment_status == "confirmed" else "⏳"
    txn_info = f" (TXN-{ticket.payment_transaction_id})" if ticket.payment_transaction_id else ""

    lines = [
        f"🛍 NEW ORDER #{ticket.ticket_number:05d}",
        "",
        f"🗓 Date: {ticket.created_at.strftime('%d.%m.%Y, %H:%M')}",
        f"👤 Instagram: @{ticket.client_instagram}",
    ]
    if ticket.client_name:
        lines.append(f"✏️ Name: {ticket.client_name}")
    if ticket.client_phone:
        lines.append(f"📞 Phone: {ticket.client_phone}")
    if ticket.client_city:
        lines.append(f"📍 City: {ticket.client_city}")
    if ticket.client_address:
        lines.append(f"🏠 Address: {ticket.client_address}")

    lines += [
        "",
        f"📦 Product: {ticket.product_name} x{ticket.product_quantity}",
        f"💰 Total: {ticket.total_amount:,} UZS",
        "",
        f"💳 Payment: {'Card transfer' if ticket.payment_method == 'transfer' else 'Cash'}",
        f"{status_icon} Status: {ticket.payment_status.capitalize()}{txn_info}",
    ]

    if ticket.notes:
        lines += ["", f"💬 Note: {ticket.notes}"]

    return "\n".join(lines)


async def send_order_ticket(ticket) -> None:
    """Send a formatted ticket to the Telegram operator group."""
    from app.database import AsyncSessionLocal
    from app.models import Ticket
    from sqlalchemy import select

    bot = get_bot()
    text = _format_ticket_message(ticket)
    keyboard = _build_ticket_keyboard(str(ticket.id), ticket.order_status)

    msg = await bot.send_message(
        chat_id=settings.telegram_group_id,
        text=text,
        reply_markup=keyboard,
    )

    logger.info(
        "telegram_ticket_sent",
        ticket_id=str(ticket.id),
        telegram_message_id=msg.message_id,
    )

    # Persist telegram_message_id
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Ticket).where(Ticket.id == ticket.id))
        db_ticket = result.scalar_one_or_none()
        if db_ticket:
            db_ticket.telegram_message_id = msg.message_id
            await db.commit()


async def edit_ticket_message(telegram_message_id: int, ticket) -> None:
    """Edit an existing Telegram ticket message to reflect new status."""
    bot = get_bot()
    text = _format_ticket_message(ticket)
    keyboard = _build_ticket_keyboard(str(ticket.id), ticket.order_status)
    try:
        await bot.edit_message_text(
            chat_id=settings.telegram_group_id,
            message_id=telegram_message_id,
            text=text,
            reply_markup=keyboard,
        )
    except Exception as exc:
        logger.warning("telegram_edit_message_failed", error=str(exc))


async def send_admin_alert(message: str) -> None:
    """Send an alert message to the operator group."""
    bot = get_bot()
    try:
        await bot.send_message(
            chat_id=settings.telegram_group_id,
            text=f"⚠️ SYSTEM ALERT\n{message}",
        )
    except Exception as exc:
        logger.error("telegram_admin_alert_failed", error=str(exc))


# --- Callback handler for inline buttons ---

async def handle_ticket_callback(callback: CallbackQuery):
    """Handle Take/Complete/Cancel button presses from Telegram operators."""
    from app.database import AsyncSessionLocal
    from app.models import Ticket
    from sqlalchemy import select
    from datetime import datetime, timezone

    data = callback.data  # "ticket:{uuid}:{action}"
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "ticket":
        await callback.answer("Invalid callback")
        return

    _, ticket_id_str, action = parts
    operator_name = callback.from_user.full_name or callback.from_user.username or "Operator"

    status_map = {
        "take": "in_progress",
        "complete": "completed",
        "cancel": "cancelled",
    }
    new_status = status_map.get(action)
    if not new_status:
        await callback.answer("Unknown action")
        return

    import uuid
    try:
        ticket_uuid = uuid.UUID(ticket_id_str)
    except ValueError:
        await callback.answer("Invalid ticket ID")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Ticket).where(Ticket.id == ticket_uuid))
        ticket = result.scalar_one_or_none()
        if not ticket:
            await callback.answer("Ticket not found")
            return

        ticket.order_status = new_status
        ticket.updated_at = datetime.now(timezone.utc)
        if action == "take":
            ticket.notes = (ticket.notes or "") + f"\nTaken by: {operator_name}"
        await db.commit()
        await db.refresh(ticket)

    await edit_ticket_message(callback.message.message_id, ticket)
    await callback.answer(f"Status updated: {new_status}")
    logger.info(
        "telegram_ticket_action",
        ticket_id=ticket_id_str,
        action=action,
        operator=operator_name,
    )


async def start_telegram_polling():
    """Start polling in background (used in development; production uses webhooks or long-polling worker)."""
    global _dp
    bot = get_bot()
    _dp = Dispatcher()
    _dp.callback_query.register(handle_ticket_callback, F.data.startswith("ticket:"))
    await _dp.start_polling(bot, allowed_updates=["callback_query"])


async def close_telegram():
    global _bot
    if _bot:
        await _bot.session.close()
        _bot = None
