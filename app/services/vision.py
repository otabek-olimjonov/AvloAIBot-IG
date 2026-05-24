import asyncio
import base64

import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

genai.configure(api_key=settings.gemini_api_key)
_vision_model = genai.GenerativeModel(settings.gemini_model)

VISION_PROMPT_TEMPLATE = """Analyze this payment screenshot from an Uzbek banking app (Uzcard, Humo, Click, Payme). Extract the following data:
1. Transaction amount (in UZS)
2. Transaction ID / receipt number
3. Date and time of transaction
4. Sender card number (last 4 digits)
5. Transaction status (successful / pending / failed)

Expected payment amount: {expected_amount} UZS

Respond ONLY with valid JSON, no markdown:
{{
  "amount": 175000,
  "transaction_id": "TXN-123456",
  "date": "2026-05-12 14:32",
  "sender_card_last4": "1234",
  "status": "successful",
  "amount_matches": true,
  "confidence": "high",
  "issues": []
}}"""


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
async def analyze_payment_screenshot(image_bytes: bytes, expected_amount: int) -> dict:
    """Send payment screenshot to Gemini Vision and parse the result."""
    import json

    prompt = VISION_PROMPT_TEMPLATE.format(expected_amount=expected_amount)

    image_part = {
        "inline_data": {
            "mime_type": "image/jpeg",
            "data": base64.b64encode(image_bytes).decode(),
        }
    }

    start = asyncio.get_event_loop().time()
    response = await asyncio.to_thread(
        _vision_model.generate_content,
        [prompt, image_part],
    )
    elapsed = asyncio.get_event_loop().time() - start

    logger.info(
        "gemini_vision_call",
        elapsed_ms=round(elapsed * 1000),
        expected_amount=expected_amount,
    )

    raw = response.text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    result = json.loads(raw)

    # Validate confidence field
    if result.get("confidence") not in ("high", "medium", "low"):
        result["confidence"] = "low"

    return result


def determine_payment_action(vision_result: dict) -> tuple[str, str]:
    """
    Returns (payment_status, bot_reply_hint).
    payment_status: 'confirmed' | 'pending'
    bot_reply_hint: 'auto_confirm' | 'flag_confirm' | 'request_resend' | 'not_screenshot'
    """
    amount_matches = vision_result.get("amount_matches", False)
    confidence = vision_result.get("confidence", "low")

    if amount_matches and confidence == "high":
        return "confirmed", "auto_confirm"
    elif amount_matches and confidence == "medium":
        return "confirmed", "flag_confirm"
    elif not vision_result.get("amount") and not vision_result.get("transaction_id"):
        return "pending", "not_screenshot"
    else:
        return "pending", "request_resend"
