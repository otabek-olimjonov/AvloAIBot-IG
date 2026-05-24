"""
Seed script — inserts initial data into the database.
Run: python -m scripts.seed
"""
import asyncio
from app.database import AsyncSessionLocal, engine, Base
from app.models import Product, Prompt, Setting, User
from app.services.auth import hash_password


PRODUCTS = [
    {
        "name": "Lavender Pillow Classic",
        "description": "Classic pillow with natural lavender for better sleep. Helps relieve stress and improve sleep quality.",
        "price": 175_000,
        "is_available": True,
    },
    {
        "name": "Lavender Pillow Premium",
        "description": "Premium pillow with double lavender fill. Extra therapeutic benefits for deep, restful sleep.",
        "price": 250_000,
        "is_available": True,
    },
    {
        "name": "Lavender Pillow Mini",
        "description": "Compact pillow, perfect as a gift. Great for travel and as a decorative aromatherapy item.",
        "price": 95_000,
        "is_available": True,
    },
    {
        "name": "Sweet Dreams Set (2 pcs)",
        "description": "Bundle deal: two Classic pillows at a discount. Perfect for couples or as a family gift.",
        "price": 299_000,
        "is_available": True,
    },
]

PROMPTS = [
    {
        "type": "system",
        "content": (
            "You are a friendly and professional sales assistant for a lavender pillow brand in Uzbekistan. "
            "Respond in the same language the customer uses (Uzbek or Russian). "
            "Never make up information not in the product catalog. "
            "Be warm, helpful, and guide the customer toward a purchase. "
            "Use a conversational tone. Never be pushy. "
            "Always respond in valid JSON as instructed."
        ),
    },
    {
        "type": "greeting",
        "content": (
            "Greet the customer warmly. Introduce yourself as a sales assistant. "
            "Ask what brings them here today and how you can help. "
            "Keep it brief and friendly."
        ),
    },
    {
        "type": "qualification",
        "content": (
            "Ask the customer qualifying questions: "
            "Who is the pillow for (themselves, a gift, family)? "
            "What are their sleep problems or preferences? "
            "This helps you recommend the right product."
        ),
    },
    {
        "type": "presentation",
        "content": (
            "Present the most suitable product based on what you learned. "
            "Highlight the benefits: natural lavender scent, better sleep, stress relief. "
            "Mention the price clearly. If a promotion applies, mention it. "
            "Ask if they have any questions."
        ),
    },
    {
        "type": "objections",
        "content": (
            "Handle objections empathetically. Common concerns: "
            "Price too high → mention value and quality, offer bundle if applicable. "
            "Unsure if it works → share product benefits and natural ingredients. "
            "Delivery concerns → confirm we deliver across all of Uzbekistan. "
            "Acknowledge their concern, then pivot back to value."
        ),
    },
    {
        "type": "closing",
        "content": (
            "The customer is ready to buy. Confirm their order details: "
            "full name, phone number, city, and delivery address. "
            "Confirm the product and quantity. "
            "Then move to payment instructions."
        ),
    },
    {
        "type": "upsell",
        "content": (
            "After the customer has chosen a product, suggest an upgrade or bundle: "
            "If they chose Classic, mention Premium for better quality. "
            "If they chose 1 piece, mention the Sweet Dreams Set (2 pcs) as a better deal. "
            "Keep it light — one suggestion only."
        ),
    },
]

DEFAULT_SETTINGS = {
    "payment_card_number": "",
    "payment_card_owner": "",
    "payment_bank": "",
    "telegram_bot_token": "",
    "telegram_group_id": "",
    "instagram_page_id": "",
    "instagram_access_token": "",
    "instagram_verify_token": "",
    "timezone": "Asia/Tashkent",
    "working_hours_start": "09:00",
    "working_hours_end": "22:00",
    "is_24_7": "true",
    "offline_message": "Assalomu alaykum! Hozir ish soatlaridan tashqaridamiz. Tez orada javob beramiz. / Здравствуйте! Мы сейчас вне рабочего времени. Ответим вам скоро.",
    "fallback_message_uz": "Kechirasiz, hozir texnik nosozlik yuz berdi. Tez orada jamoamiz siz bilan bog'lanadi.",
    "fallback_message_ru": "Извините, произошла техническая ошибка. Наша команда свяжется с вами в ближайшее время.",
}


async def seed():
    async with AsyncSessionLocal() as db:
        # Products
        from sqlalchemy import select
        existing_products = await db.execute(select(Product))
        if not existing_products.scalars().first():
            for p in PRODUCTS:
                db.add(Product(**p))
            print(f"Seeded {len(PRODUCTS)} products")
        else:
            print("Products already seeded, skipping")

        # Prompts
        existing_prompts = await db.execute(select(Prompt))
        if not existing_prompts.scalars().first():
            for p in PROMPTS:
                db.add(Prompt(**p))
            print(f"Seeded {len(PROMPTS)} prompts")
        else:
            print("Prompts already seeded, skipping")

        # Settings
        existing_settings = await db.execute(select(Setting))
        existing_keys = {s.key for s in existing_settings.scalars().all()}
        inserted = 0
        for key, value in DEFAULT_SETTINGS.items():
            if key not in existing_keys:
                db.add(Setting(key=key, value=value))
                inserted += 1
        if inserted:
            print(f"Seeded {inserted} settings")
        else:
            print("Settings already seeded, skipping")

        # Default admin user
        existing_admin = await db.execute(select(User).where(User.username == "admin"))
        if not existing_admin.scalars().first():
            db.add(User(
                username="admin",
                email="admin@localhost",
                hashed_password=hash_password("admin123"),
                role="admin",
            ))
            print("Created default admin user  →  username: admin  password: admin123")
            print("⚠️  Change this password after first login!")
        else:
            print("Admin user already exists, skipping")

        await db.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
