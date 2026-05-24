import uuid
from datetime import datetime
from pydantic import BaseModel


class TicketResponse(BaseModel):
    id: uuid.UUID
    ticket_number: int
    client_instagram: str
    client_name: str | None
    client_phone: str | None
    client_city: str | None
    client_address: str | None
    product_name: str
    product_quantity: int
    total_amount: int
    payment_method: str
    payment_status: str
    payment_screenshot_url: str | None
    payment_transaction_id: str | None
    payment_amount_verified: int | None
    order_status: str
    notes: str | None
    telegram_message_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedTickets(BaseModel):
    items: list[TicketResponse]
    total: int
    page: int
    per_page: int
