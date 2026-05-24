"""
Entrypoint for the standalone Telegram bot process.
Run as a single process — never alongside Gunicorn workers.
"""
import asyncio
import logging

from app.services.telegram import start_telegram_polling

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main():
    logger.info("Telegram bot polling started")
    await start_telegram_polling()


if __name__ == "__main__":
    asyncio.run(main())
