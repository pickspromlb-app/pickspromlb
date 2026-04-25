"""
Script de prueba: verifica que el bot de Telegram funciona.
Ejecutar: python scripts/test_telegram.py
"""

import sys
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telegram import Bot
from app.utils.config import config
from loguru import logger


async def main():
    logger.info("🤖 Probando bot de Telegram...")
    
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("❌ Falta TELEGRAM_BOT_TOKEN en .env")
        return False
    
    try:
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        info = await bot.get_me()
        
        logger.info(f"✅ Bot conectado:")
        logger.info(f"   Nombre: {info.first_name}")
        logger.info(f"   Username: @{info.username}")
        logger.info(f"   ID: {info.id}")
        
        if config.TELEGRAM_CHAT_ID:
            logger.info(f"📤 Enviando mensaje de prueba al chat {config.TELEGRAM_CHAT_ID}...")
            await bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text="✅ *Test exitoso!*\n\nEl bot de PicksProMLB está funcionando correctamente.",
                parse_mode="Markdown"
            )
            logger.info("✅ Mensaje enviado")
        else:
            logger.warning("⚠️ TELEGRAM_CHAT_ID no configurado")
            logger.info("Para obtener tu chat_id:")
            logger.info(f"   1. Abre @{info.username} en Telegram")
            logger.info("   2. Envíale /start")
            logger.info("   3. El bot te dará tu chat_id")
        
        return True
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
