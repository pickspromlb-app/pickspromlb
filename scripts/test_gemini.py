"""
Script de prueba: verifica que Gemini API funciona.
Ejecutar: python scripts/test_gemini.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import google.generativeai as genai
from app.utils.config import config
from loguru import logger


def main():
    logger.info("🧠 Probando Gemini API...")
    
    if not config.GEMINI_API_KEY:
        logger.error("❌ Falta GEMINI_API_KEY en .env")
        return False
    
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        
        # Listar modelos disponibles
        logger.info("📋 Modelos disponibles:")
        for model in genai.list_models():
            if "generateContent" in model.supported_generation_methods:
                logger.info(f"   • {model.name}")
        
        # Probar con un prompt simple
        logger.info(f"\n🧪 Probando modelo {config.GEMINI_MODEL}...")
        model = genai.GenerativeModel(config.GEMINI_MODEL)
        response = model.generate_content("Responde con una sola palabra: ¿está funcionando? Responde 'sí' o 'no'.")
        
        logger.info(f"✅ Respuesta de Gemini: {response.text.strip()}")
        return True
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
