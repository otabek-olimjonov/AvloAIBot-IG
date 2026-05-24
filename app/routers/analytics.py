from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Conversation, Ticket
from app.services.auth import get_current_user, require_admin, UserInfo

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(get_current_user),
):
    today = date.today()
    today_start = datetime(today.year, today.month, today.day, 0, 0, 0)
    today_end = datetime(today.year, today.month, today.day, 23, 59, 59)

    # Today's conversations
    conv_result = await db.execute(
        select(func.count(Conversation.id)).where(
            Conversation.started_at >= today_start,
        )
    )
    today_conversations = conv_result.scalar_one()

    # Today's orders (converted conversations = tickets created today)
    orders_result = await db.execute(
        select(func.count(Ticket.id)).where(
            Ticket.created_at >= today_start,
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
    since = date.today() - timedelta(days=days)
    since_dt = datetime(since.year, since.month, since.day, 0, 0, 0)

    conv_result = await db.execute(
        select(
            cast(Conversation.started_at, Date).label("day"),
            func.count(Conversation.id).label("count"),
        )
        .where(Conversation.started_at >= since_dt)
        .group_by("day")
        .order_by("day")
    )
    conversations_by_day = {str(row.day): row.count for row in conv_result.all()}

    orders_result = await db.execute(
        select(
            cast(Ticket.created_at, Date).label("day"),
            func.count(Ticket.id).label("count"),
        )
        .where(Ticket.created_at >= since_dt)
        .group_by("day")
        .order_by("day")
    )
    orders_by_day = {str(row.day): row.count for row in orders_result.all()}

    # Build full date range
    labels = []
    conv_data = []
    order_data = []
    for i in range(days):
        d = str(since + timedelta(days=i))
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
