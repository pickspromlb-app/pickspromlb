"""
Script maestro: prueba TODAS las APIs configuradas.
Ejecutar: python scripts/test_all.py
"""

import sys
import asyncio
import requests
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.config import config
from loguru import logger


def test_odds_api():
    """Prueba The Odds API"""
    logger.info("\n🎲 Probando The Odds API...")
    if not config.ODDS_API_KEY:
        logger.error("❌ ODDS_API_KEY no configurada")
        return False
    
    try:
        url = "https://api.the-odds-api.com/v4/sports"
        response = requests.get(url, params={"apiKey": config.ODDS_API_KEY}, timeout=10)
        response.raise_for_status()
        sports = response.json()
        
        mlb = next((s for s in sports if s.get("key") == "baseball_mlb"), None)
        if mlb:
            logger.info(f"✅ Odds API OK")
            logger.info(f"   Requests usadas: {response.headers.get('x-requests-used', '?')}")
            logger.info(f"   Requests restantes: {response.headers.get('x-requests-remaining', '?')}")
            return True
        else:
            logger.warning("⚠️ MLB no encontrado en deportes")
            return False
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False


def test_weather_api():
    """Prueba OpenWeather API"""
    logger.info("\n🌤️ Probando OpenWeather API...")
    if not config.OPENWEATHER_API_KEY:
        logger.error("❌ OPENWEATHER_API_KEY no configurada")
        return False
    
    try:
        # Coordenadas de Yankee Stadium
        url = "https://api.openweathermap.org/data/2.5/weather"
        response = requests.get(
            url,
            params={
                "lat": 40.8296,
                "lon": -73.9262,
                "appid": config.OPENWEATHER_API_KEY,
                "units": "imperial",
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        logger.info(f"✅ Weather API OK")
        logger.info(f"   Yankee Stadium: {data['main']['temp']}°F, {data['weather'][0]['description']}")
        return True
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False


def test_mlb_stats_api():
    """Prueba MLB Stats API (no requiere key)"""
    logger.info("\n⚾ Probando MLB Stats API...")
    try:
        import statsapi
        from datetime import date
        
        schedule = statsapi.schedule(date=date.today().strftime("%Y-%m-%d"))
        logger.info(f"✅ MLB Stats API OK ({len(schedule)} juegos hoy)")
        return True
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False


async def main():
    logger.info("🔍 ===== TESTEANDO TODAS LAS APIs =====\n")
    
    results = {}
    
    # Supabase
    logger.info("📊 Probando Supabase...")
    try:
        from app.utils.database import db
        db.select("efectividad_filtros")
        results["Supabase"] = True
        logger.info("✅ Supabase OK")
    except Exception as e:
        results["Supabase"] = False
        logger.error(f"❌ Supabase: {e}")
    
    # Telegram
    logger.info("\n🤖 Probando Telegram...")
    try:
        from telegram import Bot
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        info = await bot.get_me()
        results["Telegram"] = True
        logger.info(f"✅ Telegram OK (@{info.username})")
    except Exception as e:
        results["Telegram"] = False
        logger.error(f"❌ Telegram: {e}")
    
    # Gemini
    logger.info("\n🧠 Probando Gemini...")
    try:
        import google.generativeai as genai
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(config.GEMINI_MODEL)
        response = model.generate_content("Responde 'OK'")
        results["Gemini"] = True
        logger.info(f"✅ Gemini OK ({response.text.strip()[:20]})")
    except Exception as e:
        results["Gemini"] = False
        logger.error(f"❌ Gemini: {e}")
    
    # Otras APIs
    results["Odds API"] = test_odds_api()
    results["Weather API"] = test_weather_api()
    results["MLB Stats API"] = test_mlb_stats_api()
    
    # Resumen
    logger.info("\n📊 ===== RESUMEN =====")
    for name, ok in results.items():
        emoji = "✅" if ok else "❌"
        logger.info(f"{emoji} {name}")
    
    todos_ok = all(results.values())
    if todos_ok:
        logger.info("\n🎉 ¡TODAS LAS APIs FUNCIONAN! Sistema listo.")
    else:
        logger.error("\n⚠️ Algunas APIs fallaron. Revisa el .env")
    
    return todos_ok


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
