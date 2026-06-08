"""
Update script — rewrites products and prompts in the live database with Lavanda Yostiq content.
Run: python -m scripts.update_lavanda
"""
import asyncio
from sqlalchemy import select, update, delete
from app.database import AsyncSessionLocal
from app.models import Product, Prompt, Setting
from scripts.seed import PRODUCTS, PROMPTS


async def update():
    async with AsyncSessionLocal() as db:
        # Replace all products
        await db.execute(delete(Product))
        for p in PRODUCTS:
            db.add(Product(**p))
        print(f"Replaced products ({len(PRODUCTS)} items)")

        # Replace all prompts
        await db.execute(delete(Prompt))
        for p in PROMPTS:
            db.add(Prompt(**p))
        print(f"Replaced prompts ({len(PROMPTS)} items)")

        # Update DM/comment messages
        dm_updates = {
            "comment_auto_dm_message": (
                "Salom, {name}! 👋 Izohingiz uchun rahmat 🌸\n"
                "Lavanda yostiqlari haqida ko'proq bilmoqchimisiz? "
                "Men Laylo — sizga eng mos variantni topishga yordam beraman. Shunchaki yozing! 😊"
            ),
            "dm_greeting_message": (
                "Assalomu alaykum! 👋 Lavanda yostiq do'koniga xush kelibsiz.\n"
                "Men Laylo — sizning shaxsiy konsultantingizman 🌸\n"
                "Ismingiz nima? Sizga eng mos mahsulotni topishga yordam beraman 😊"
            ),
            "comment_reply_message": (
                "Salom, {name}! 😊 DM ga yozib qoldingiz — tez orada javob beramiz! 🌿"
            ),
        }
        for key, value in dm_updates.items():
            result = await db.execute(select(Setting).where(Setting.key == key))
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = value
                print(f"Updated setting: {key}")
            else:
                db.add(Setting(key=key, value=value))
                print(f"Inserted setting: {key}")

        await db.commit()
        print("Update complete.")


if __name__ == "__main__":
    asyncio.run(update())
