import json
import asyncio
from datetime import date

import google.generativeai as genai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

genai.configure(api_key=settings.gemini_api_key)

_model = genai.GenerativeModel(settings.gemini_model)

RESPONSE_FORMAT_INSTRUCTIONS = """
Respond ONLY with valid JSON in this exact format (no markdown, no explanation):
{
  "reply": "Message text to send to client",
  "funnel_stage": "greeting|qualification|presentation|objection|closing|payment|completed",
  "intent": "buying|question|objection|confirm_order|send_payment|other",
  "extracted_data": {
    "client_name": null,
    "client_phone": null,
    "client_city": null,
    "client_address": null,
    "product_name": null,
    "product_quantity": null,
    "total_amount": null
  }
}
Only include extracted_data fields you can confirm from the conversation. Use null for unknown fields.
"""


PAYMENT_HINT_TEXT = {
    "auto_confirm": "Payment screenshot verified automatically — amount matches and confidence is high. Confirm the order and move to completed stage.",
    "flag_confirm": "Payment screenshot received — amount matches but confidence is medium. Accept and move to completed stage, but note it for manual review.",
    "request_resend": "Payment screenshot could not be verified — amount mismatch or unclear image. Politely ask the customer to resend a clearer screenshot.",
    "not_screenshot": "The image sent does not appear to be a payment screenshot. Politely inform the customer and ask them to send the payment receipt.",
}


def _build_prompt(
    system_prompt: str,
    products: list[dict],
    promotions: list[dict],
    sales_script: str,
    faq_items: list[dict],
    history: list[dict],
    current_message: str,
    current_message_has_image: bool = False,
    payment_hint: str | None = None,
) -> str:
    products_text = "\n".join(
        f"- {p['name']}: {p['description'] or ''} | Price: {p['price']:,} UZS"
        for p in products
    )

    promotions_text = ""
    if promotions:
        today = date.today()
        active = [
            p for p in promotions
            if p.get("is_active") and p.get("start_date") <= today <= p.get("end_date")
        ]
        if active:
            promotions_text = "\n## Active Promotions\n" + "\n".join(
                f"- {p['name']}: {p.get('description_for_bot', p['value'])}"
                + (f" | Code: {p['promo_code']}" if p.get("promo_code") else "")
                for p in active
            )

    faq_text = "\n".join(
        f"Q: {f['question']}\nA: {f['answer']}" for f in faq_items
    )

    history_text = "\n".join(
        f"{'Client' if m['role'] == 'client' else 'Bot'}: {m['content']}"
        for m in history
    )

    image_note = "\n[The client has sent an image with this message.]" if current_message_has_image else ""
    payment_hint_note = (
        f"\n\n## Payment Verification Result\n{PAYMENT_HINT_TEXT[payment_hint]}"
        if payment_hint and payment_hint in PAYMENT_HINT_TEXT
        else ""
    )

    return f"""{system_prompt}

## Product Catalog
{products_text}
{promotions_text}

## Sales Script for Current Stage
{sales_script}

## FAQ
{faq_text}

## Conversation History
{history_text}

## Current Client Message
{current_message}{image_note}{payment_hint_note}

## Instructions
{RESPONSE_FORMAT_INSTRUCTIONS}"""


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
async def _call_gemini_text(prompt: str) -> str:
    start = asyncio.get_event_loop().time()
    response = await asyncio.to_thread(_model.generate_content, prompt)
    elapsed = asyncio.get_event_loop().time() - start

    usage = getattr(response, "usage_metadata", None)
    logger.info(
        "gemini_text_call",
        elapsed_ms=round(elapsed * 1000),
        input_tokens=getattr(usage, "prompt_token_count", None),
        output_tokens=getattr(usage, "candidates_token_count", None),
    )
    return response.text


def _parse_gemini_response(raw: str) -> dict:
    """Strip markdown fences if present and parse JSON."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


VALID_FUNNEL_STAGES = {
    "greeting", "qualification", "presentation",
    "objection", "closing", "payment", "completed",
}
VALID_INTENTS = {
    "buying", "question", "objection", "confirm_order", "send_payment", "other",
}


async def generate_sales_response(
    system_prompt: str,
    products: list[dict],
    promotions: list[dict],
    sales_script: str,
    faq_items: list[dict],
    history: list[dict],
    current_message: str,
    current_message_has_image: bool = False,
    payment_hint: str | None = None,
) -> dict:
    """
    Call Gemini and return a parsed response dict with keys:
    reply, funnel_stage, intent, extracted_data
    """
    prompt = _build_prompt(
        system_prompt=system_prompt,
        products=products,
        promotions=promotions,
        sales_script=sales_script,
        faq_items=faq_items,
        history=history,
        current_message=current_message,
        current_message_has_image=current_message_has_image,
        payment_hint=payment_hint,
    )

    raw = await _call_gemini_text(prompt)
    result = _parse_gemini_response(raw)

    # Sanitize stage / intent to prevent injection from LLM output
    if result.get("funnel_stage") not in VALID_FUNNEL_STAGES:
        result["funnel_stage"] = "greeting"
    if result.get("intent") not in VALID_INTENTS:
        result["intent"] = "other"

    return result


FALLBACK_MESSAGE_UZ = (
    "Kechirasiz, hozir texnik nosozlik yuz berdi. "
    "Tez orada jamoamiz siz bilan bog'lanadi."
)
FALLBACK_MESSAGE_RU = (
    "Извините, произошла техническая ошибка. "
    "Наша команда свяжется с вами в ближайшее время."
)
