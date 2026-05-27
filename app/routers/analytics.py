from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, cast, Date, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Conversation, Ticket, Setting
from app.services.auth import get_current_user, UserInfo

router = APIRouter(prefix="/analytics", tags=["analytics"])


async def _get_business_tz(db: AsyncSession) -> ZoneInfo:
    """Read the configured timezone from DB settings (falls back to Tashkent)."""
    result = await db.execute(
        select(Setting.value).where(Setting.key == "timezone")
    )
    tz_name = result.scalar_one_or_none() or "Asia/Tashkent"
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        return ZoneInfo("Asia/Tashkent")


def _today_bounds_naive_utc(tz: ZoneInfo) -> tuple[datetime, datetime]:
    """
    Return (start_of_today_utc, end_of_today_utc) as *naive* UTC datetimes.

    The DB columns are TIMESTAMP WITHOUT TIME ZONE storing UTC values.
    asyncpg rejects tz-aware datetimes for such columns, so we strip tzinfo
    after converting to UTC.
    """
    local_now = datetime.now(tz)
    local_today = local_now.date()
    start_local = datetime(local_today.year, local_today.month, local_today.day, tzinfo=tz)
    end_local = start_local + timedelta(days=1, microseconds=-1)
    # Convert to UTC then strip tzinfo so asyncpg can bind to TIMESTAMP WITHOUT TIME ZONE
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


def _local_day_expr(col, tz_key: str):
    """
    SQLAlchemy expression that converts a naive-UTC TIMESTAMP column to
    a local-timezone DATE for grouping.

    PostgreSQL semantics:
      timezone(zone, naive_ts)  -> treats naive_ts as being IN zone (wrong for UTC columns)
      timezone(zone, timezone('UTC', naive_ts))  -> first tags it as UTC, then converts (correct)
    """
    return cast(
        func.timezone(text(f"'{tz_key}'"), func.timezone(text("'UTC'"), col)),
        Date,
    )


@router.get("/dashboard")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(get_current_user),
):
    tz = await _get_business_tz(db)
    today_start, today_end = _today_bounds_naive_utc(tz)

    # Today's conversations
    conv_result = await db.execute(
        select(func.count(Conversation.id)).where(
            Conversation.started_at >= today_start,
            Conversation.started_at <= today_end,
        )
    )
    today_conversations = conv_result.scalar_one()

    # Today's orders (tickets created today)
    orders_result = await db.execute(
        select(func.count(Ticket.id)).where(
            Ticket.created_at >= today_start,
            Ticket.created_at <= today_end,
        )
    )
    today_orders = orders_result.scalar_one()

    # Conversion rate
    conversion_rate = (
        round(today_orders / today_conversations * 100, 2)
        if today_conversations > 0
        else 0.0
    )

    # Today's revenue (confirmed payments)
    revenue_result = await db.execute(
        select(func.coalesce(func.sum(Ticket.total_amount), 0)).where(
            Ticket.created_at >= today_start,
            Ticket.created_at <= today_end,
            Ticket.payment_status == "confirmed",
        )
    )
    today_revenue = revenue_result.scalar_one()

    return {
        "today_conversations": today_conversations,
        "today_orders": today_orders,
        "conversion_rate": conversion_rate,
        "today_revenue": today_revenue,
    }


@router.get("/chart")
async def chart(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(get_current_user),
):
    tz = await _get_business_tz(db)
    local_today = datetime.now(tz).date()
    since_local = local_today - timedelta(days=days - 1)

    # Naive UTC bound (DB stores naive UTC)
    since_utc = (
        datetime(since_local.year, since_local.month, since_local.day, tzinfo=tz)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )

    conv_result = await db.execute(
        select(
            _local_day_expr(Conversation.started_at, tz.key).label("day"),
            func.count(Conversation.id).label("count"),
        )
        .where(Conversation.started_at >= since_utc)
        .group_by("day")
        .order_by("day")
    )
    conversations_by_day = {str(row.day): row.count for row in conv_result.all()}

    orders_result = await db.execute(
        select(
            _local_day_expr(Ticket.created_at, tz.key).label("day"),
            func.count(Ticket.id).label("count"),
        )
        .where(Ticket.created_at >= since_utc)
        .group_by("day")
        .order_by("day")
    )
    orders_by_day = {str(row.day): row.count for row in orders_result.all()}

    # Build full date range in business's local days
    labels = []
    conv_data = []
    order_data = []
    for i in range(days):
        d = str(since_local + timedelta(days=i))
        labels.append(d)
        conv_data.append(conversations_by_day.get(d, 0))
        order_data.append(orders_by_day.get(d, 0))

    return {"labels": labels, "conversations": conv_data, "orders": order_data}


@router.get("/products")
async def products_breakdown(
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(get_current_user),
):
    result = await db.execute(
        select(
            Ticket.product_name,
            func.count(Ticket.id).label("count"),
            func.coalesce(func.sum(Ticket.total_amount), 0).label("revenue"),
        )
        .group_by(Ticket.product_name)
        .order_by(func.count(Ticket.id).desc())
    )
    return [
        {"product": row.product_name, "count": row.count, "revenue": row.revenue}
        for row in result.all()
    ]
