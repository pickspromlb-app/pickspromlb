"""
Script de prueba: verifica que la conexión a Supabase funciona.
Ejecutar: python scripts/test_supabase.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.config import config
from app.utils.database import db
from loguru import logger


def main():
    logger.info("🔍 Probando conexión a Supabase...")
    
    if not config.SUPABASE_URL or not config.SUPABASE_KEY:
        logger.error("❌ Faltan SUPABASE_URL o SUPABASE_KEY en .env")
        return False
    
    try:
        client = db.get_client()
        
        # Intentar consultar tabla efectividad_filtros
        logger.info("📊 Consultando tabla efectividad_filtros...")
        result = db.select("efectividad_filtros")
        logger.info(f"✅ Conexión OK - {len(result)} filtros encontrados")
        
        for f in result:
            logger.info(f"   {f['filtro']}: {f['porcentaje_efectividad']}% - {f['descripcion']}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        logger.error("\n💡 Posibles causas:")
        logger.error("   1. SUPABASE_URL incorrecta")
        logger.error("   2. SUPABASE_KEY incorrecta (debe ser secret/service_role)")
        logger.error("   3. No has ejecutado el SQL schema (sql/01_schema.sql)")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
