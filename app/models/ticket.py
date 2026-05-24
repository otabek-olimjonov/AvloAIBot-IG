import uuid
from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, Integer, Sequence, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


ticket_number_seq = Sequence("ticket_number_seq", start=1)


class Ticket(Base):
    __tablename__ = "tickets"

    __table_args__ = (
        CheckConstraint(
            "payment_method IN ('transfer', 'cash')", name="ck_tickets_payment_method"
        ),
        CheckConstraint(
            "payment_status IN ('confirmed', 'pending', 'rejected')",
            name="ck_tickets_payment_status",
        ),
        CheckConstraint(
            "order_status IN ('new', 'in_progress', 'completed', 'cancelled')",
            name="ck_tickets_order_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticket_number: Mapped[int] = mapped_column(
        Integer,
        ticket_number_seq,
        server_default=ticket_number_seq.next_value(),
        nullable=False,
        unique=True,
    )
    client_instagram: Mapped[str] = mapped_column(Text, nullable=False)
    client_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_city: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_name: Mapped[str] = mapped_column(Text, nullable=False)
    product_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_method: Mapped[str] = mapped_column(Text, nullable=False)
    payment_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    payment_screenshot_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_transaction_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_amount_verified: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_status: Mapped[str] = mapped_column(Text, nullable=False, default="new")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
