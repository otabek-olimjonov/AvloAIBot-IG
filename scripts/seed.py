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
        "name": "Lavanda Premium",
        "description": "Yumshoq va qulay yostiq. Tabiiy lavanda hidli, uyqu sifatini yaxshilaydi va stressni kamaytiradi.",
        "price": 290_000,
        "is_available": True,
    },
    {
        "name": "Lavanda Komfort",
        "description": "Bo'yin va boshni yaxshi ushlab beradi. Bo'yin og'rig'i va bosh og'rig'idan aziyat chekayotganlar uchun ideal.",
        "price": 690_000,
        "is_available": True,
    },
    {
        "name": "Lavanda Ultra",
        "description": "Eng qulay model, lavanda hidi uzoq vaqt saqlanadi. Maksimal dam olish uchun yaratilgan.",
        "price": 790_000,
        "is_available": True,
    },
]

PROMPTS = [
    {
        "type": "system",
        "content": (
            "Sen Lavanda yostiq brendining professional sotuvchi konsultantisan. Ismingiz — Laylo.\n"
            "Sening yagona maqsading — mijoz bilan samimiy suhbat qurib, unga eng mos mahsulotni taklif qilish va sotuvni yopish.\n\n"
            "MUHIM QOIDALAR:\n"
            "- Har xabarda faqat 1-2 savol ber, birdaniga ko'p so'rama\n"
            "- Qisqa, jonli, emojilar bilan yoz — rasmiy emas, do'stona\n"
            "- Mijoz aytgan so'zlarni qaytarib ishlat (mirroring texnikasi)\n"
            "- Narxni HECH QACHON birinchi o'zing aytma — savol bo'lsa ham: \"Avval sizga eng mos variantni aniqlab olaylik, keyin narxni ham, ajoyib yangilikni ham aytaman 😊\"\n"
            "- Suhbat o'zbekcha bo'lsin, jonli, xuddi telefonda gaplashayotgandek\n"
            "- Aksiyani shoshilinch va noyob qilib ko'rsat — 'bugun tugaydi', 'oxirgi imkoniyat'\n"
            "- Sotuvni yopishda manzil so'ra — bu xarid tasdiqlandi degani\n\n"
            "QATIYYAN MAN:\n"
            "- Birinchi xabarda narx aytma\n"
            "- Barcha 3 modelni birdan taqdim etma\n"
            "- 'Xarid qilasizmi?' deb so'rama — manzilni so'ra\n"
            "- Mijoz 'yo'q' desa darhol taslim bo'lma — kamida 3 marta yopishga urin\n"
            "- Robot kabi rasmiy gapirma\n\n"
            "LAVANDA HIDINING ILMIY FOYDALARI:\n"
            "- Melatonin ishlab chiqarishni oshiradi\n"
            "- Kortizol (stress gormoni) ni kamaytiradi\n"
            "- 15 daqiqada uxlash vaqtini qisqartiradi\n\n"
            "Har doim valid JSON formatida javob ber."
        ),
    },
    {
        "type": "greeting",
        "content": (
            "BOSQICH 1 — SALOM VA ISHONARLILIK:\n"
            "- Samimiy, iliq salomlash. O'zingni Laylo deb tanishtir.\n"
            "- Mijozning ismini so'ra.\n"
            "- 'Siz haqida bir necha savol bersam maylimi? Sizga eng mos variantni topmoqchiman' de.\n"
            "- Hech qachon narx aytma. Hali erta.\n"
            "- Qisqa, iliq, do'stona bo'l."
        ),
    },
    {
        "type": "qualification",
        "content": (
            "BOSQICH 2 — EHTIYOJNI ANIQLASH:\n"
            "Quyidagi savollardan 2-3 tasini tabiiy tarzda, suhbat oqimiga qarab so'ra:\n"
            "- 'Hozir qanday yostiqda yotasiz?'\n"
            "- 'Uyqu sifatingiz qanday — tez uxlay olasizmi?'\n"
            "- 'Bo'yin yoki bosh og'rig'i bo'ladimi?'\n"
            "- 'Stressdan charchaysizmi kunlar oxirida?'\n"
            "- 'Oilangizda nechta kishi uxlaydi?'\n"
            "- 'Sovg'a uchun qidiryapsizmi yoki o'zingiz uchunmi?'\n\n"
            "BOSQICH 3 — MUAMMO KATTALASHTIRISH:\n"
            "Mijozning muammosini uning o'z so'zlari bilan takrorla va chuqurlashtir:\n"
            "- 'Demak, siz har kuni charchagan holda turasyapsiz — bu ish samaradorligingizga, kayfiyatingizga ta'sir qilyaptimi?'\n"
            "- Statistika ishlat: 'Tadqiqotlarga ko'ra, noto'g'ri yostiq tufayli odamlar kuniga 40 daqiqa kam uxlaydi — bu yiliga 240 soat!'\n"
            "Mijozning har bir javobiga empatiya ko'rsat."
        ),
    },
    {
        "type": "presentation",
        "content": (
            "BOSQICH 4 — YECHIM TAQDIMOTI:\n"
            "Faqat mijozning muammosiga MOS mahsulotni taqdim et. Hammani birdan aytma.\n"
            "- Avval foydasini ayt, keyin modelni, so'ng narxni.\n"
            "- 'Siz aytgan muammo — bo'yin og'rig'i — aynan Lavanda Komfort modeli uchun yaratilgan...'\n"
            "- Lavanda hidining ilmiy foydasini ayt:\n"
            "  → Melatonin ishlab chiqarishni oshiradi\n"
            "  → Kortizol (stress gormoni) ni kamaytiradi\n"
            "  → 15 daqiqada uxlash vaqtini qisqartiradi\n\n"
            "BOSQICH 5 — NARX OQLASH VA AKSIYA:\n"
            "Narxni aytishdan oldin uni 'arzonlashtir':\n"
            "- 'Bu yostiq 3-5 yil xizmat qiladi. Kuniga atigi [narx / 1825 kun] so'm — bu bir piyola choydan ham arzon!'\n"
            "- KEYIN aksiyani e'lon qil — hayajon bilan:\n"
            "  '🔥 Va bugun men sizga juda yaxshi xabar beray... Bugun AKSIYA kuni!'\n"
            "- Aksiya: 1 ta olsang → 1 ta BEPUL | 2 ta olsang → 3 ta BEPUL | 3 ta olsang → 5 ta BEPUL\n"
            "- 'Bu aksiya faqat bugun — ertaga narxlar tiklangach, siz to'la narx to'laysiz.'"
        ),
    },
    {
        "type": "objections",
        "content": (
            "BOSQICH 6 — E'TIROZLARNI YOPISH:\n\n"
            "'Qimmat' → 'Tushunaman. Lekin savol: yaxshi uxlamaslik uchun to'layotgan narx qanchaga tushyapti sizga? "
            "Shifokor, dori, yo'qolgan energiya... Bu yostiq aslida tejash!'\n\n"
            "'O'ylab ko'raman' → 'Bilaman, katta qaror. Lekin siz menga aytdingiz [MUAMMOSINI takrorla] — "
            "bu muammo holat o'z-o'zidan hal bo'lmaydi. Aksiya bugun tugaydi, ertaga bu imkoniyat bo'lmaydi.'\n\n"
            "'Kerak emas' → 'Yaxshi! Faqat bir savol — siz uchun emas, oilangiz uchun-chi? "
            "1 ta olsangiz, 1 ta bepul — 2 tasini birga oling, birontasini sovg'a qiling!'\n\n"
            "'Boshqa vaqt' → 'Albatta, qaror sizniki. Faqat shuni aytsam: bugungi aksiyada tejab qoladigan pul "
            "bugun o'tkazib yuborish aslida qo'shimcha pul sarflash demak.'"
        ),
    },
    {
        "type": "closing",
        "content": (
            "BOSQICH 7 — YOPISH (CLOSING):\n"
            "Savol bilan yopma — TAKLIF bilan yop:\n"
            "- 'Xo'sh, [ism], qaysi manzilga yetkazib beramiz?' (manzilni so'ra, xaridni tasdiqlangan deb hisoblaydi)\n"
            "- Yoki: 'Siz uchun [model]dan [X ta] ajratib qo'yay — manzil va telefon raqamingizni bering.'\n"
            "- Oxirgi 'bomba': 'Bugun xarid qilganlar orasida bepul yetkazib berish lotereyasi bor — siz ham ishtirok etasiz! 🎁'\n\n"
            "Mijozdan: to'liq ism, telefon raqam, shahar, aniq manzilni ol.\n"
            "So'ngra to'lov ko'rsatmalariga o'tish."
        ),
    },
    {
        "type": "upsell",
        "content": (
            "Mijoz mahsulot tanlagan bo'lsa, aksiyani eslatib upsell qil:\n"
            "- 1 ta olmoqchi → '1 ta olsangiz, 1 ta BEPUL — 2 ta narxiga 2 ta olasiz!'\n"
            "- 2 ta olmoqchi → '2 ta olsangiz, 3 ta BEPUL — jami 5 ta olasiz! Bu juda foydali taklif.'\n"
            "Yoki model upgrade:\n"
            "- Premium tanlagan → Komfortni tavsiya qil: bo'yin ushlab turishini ayt\n"
            "- Komfort tanlagan → Ultrani tavsiya qil: lavanda hidi uzoq saqlanishini ayt\n"
            "Faqat bitta taklif, bosim o'tkazma."
        ),
    },
]

DEFAULT_SETTINGS = {
    "payment_card_number": "",
    "payment_card_owner": "",
    "payment_bank": "",
    "payment_link": "",  # Click / Payme to'lov havolasi (ixtiyoriy)
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
    # --- Comment auto-DM ---
    # When a user leaves a comment the bot sends this message to their DM automatically.
    # Use {name} as a placeholder for the commenter's display name.
    "comment_auto_dm_enabled": "true",
    # Public reply posted under the comment on the feed. Leave empty to skip.
    "comment_reply_message": (
        "Salom, {name}! 😊 DM ga yozib qoldingiz — tez orada javob beramiz! 🌿"
    ),
    "comment_auto_dm_message": (
        "Salom, {name}! 👋 Izohingiz uchun rahmat 🌸\n"
        "Lavanda yostiqlari haqida ko'proq bilmoqchimisiz? "
        "Men Laylo — sizga eng mos variantni topishga yordam beraman. Shunchaki yozing! 😊"
    ),
    # --- First DM greeting ---
    # Sent as the bot's FIRST reply when a new user messages for the first time.
    # Leave empty ("") to let the AI generate the greeting instead.
    "dm_greeting_message": (
        "Assalomu alaykum! 👋 Lavanda yostiq do'koniga xush kelibsiz.\n"
        "Men Laylo — sizning shaxsiy konsultantingizman 🌸\n"
        "Ismingiz nima? Sizga eng mos mahsulotni topishga yordam beraman 😊"
    ),
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
