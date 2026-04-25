"""
Script: ejecuta el sistema completo manualmente para una fecha específica.
Útil para testing y backfill de datos.

Ejecutar: 
  python scripts/run_manual.py                    # hoy
  python scripts/run_manual.py 2026-04-25         # fecha específica
"""

import sys
import asyncio
from datetime import date, datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import PicksProOrchestrator
from loguru import logger


async def main():
    # Parsear fecha
    if len(sys.argv) > 1:
        try:
            target_date = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        except ValueError:
            logger.error(f"❌ Formato inválido. Usa YYYY-MM-DD")
            return
    else:
        target_date = date.today()
    
    logger.info(f"🚀 Ejecutando sistema completo para {target_date}")
    
    orchestrator = PicksProOrchestrator()
    analisis = await orchestrator.ejecutar_manual(target_date)
    
    if analisis:
        logger.info("\n📊 ===== ANÁLISIS GENERADO =====")
        if analisis.get("directa_del_dia"):
            d = analisis["directa_del_dia"]
            logger.info(f"⭐ DIRECTA: {d.get('juego')} → {d.get('pick')} ({d.get('cuota')})")
        
        if analisis.get("combinacion_principal"):
            c = analisis["combinacion_principal"]
            logger.info(f"🎯 COMBINACIÓN 1 (cuota total: {c.get('cuota_total')}):")
            for j in c.get("juegos", []):
                logger.info(f"   • {j.get('juego')} → {j.get('pick')}")
    

if __name__ == "__main__":
    asyncio.run(main())
