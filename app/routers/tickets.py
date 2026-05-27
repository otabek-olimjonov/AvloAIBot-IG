import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Ticket
from app.schemas.ticket import TicketResponse, TicketStatusUpdate, PaginatedTickets
from app.services.auth import get_current_user, require_admin, UserInfo

router = APIRouter(prefix="/tickets", tags=["tickets"])

VALID_ORDER_STATUSES = {"new", "in_progress", "completed", "cancelled"}


@router.get("", response_model=PaginatedTickets)
async def list_tickets(
    order_status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(get_current_user),
):
    query = select(Ticket)
    if order_status:
        query = query.where(Ticket.order_status == order_status)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    query = query.order_by(Ticket.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedTickets(items=items, total=total, page=page, per_page=per_page)


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(get_current_user),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.patch("/{ticket_id}", response_model=TicketResponse)
async def update_ticket_status(
    ticket_id: uuid.UUID,
    body: TicketStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user),
):
    """Update a ticket's order_status from the admin panel."""
    if body.order_status not in VALID_ORDER_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"order_status must be one of: {', '.join(sorted(VALID_ORDER_STATUSES))}",
        )

    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.order_status = body.order_status
    ticket.updated_at = datetime.now(timezone.utc)
    if body.notes is not None:
        ticket.notes = body.notes

    await db.commit()
    await db.refresh(ticket)

    # Sync status change to Telegram message if it exists
    if ticket.telegram_message_id:
        from app.services.telegram import edit_ticket_message
        try:
            await edit_ticket_message(ticket.telegram_message_id, ticket)
        except Exception:
            pass  # Telegram sync failure is non-critical

    return ticket
