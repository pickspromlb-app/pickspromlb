"""
PicksProMLB - Agente de Análisis con Gemini
Analiza el JSON del listín y genera picks recomendados
"""

import json
from datetime import date
from typing import Dict, Optional
from loguru import logger
import google.generativeai as genai

from app.utils.config import config
from app.utils.database import db
from app.agent.system_prompt import SYSTEM_PROMPT, get_user_prompt
from app.exports.json_builder import ListinJSONBuilder


class GeminiAgent:
    """Agente que usa Gemini para analizar el listín y generar picks"""
    
    def __init__(self):
        if not config.GEMINI_API_KEY:
            logger.error("❌ GEMINI_API_KEY no configurada")
            raise ValueError("GEMINI_API_KEY requerida")
        
        genai.configure(api_key=config.GEMINI_API_KEY)
        
        # Configurar modelo con el system prompt
        self.model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
            generation_config={
                "temperature": 0.2,  # Bajo para análisis consistente
                "top_p": 0.95,
                "max_output_tokens": 8192,
                "response_mime_type": "application/json",  # Forzar JSON
            }
        )
        logger.info(f"✅ Gemini Agent inicializado con modelo: {config.GEMINI_MODEL}")
    
    def analizar_listin(self, listin: Dict) -> Optional[Dict]:
        """
        Analiza un listín completo y retorna las jugadas recomendadas.
        """
        if not listin or not listin.get("juegos"):
            logger.warning("⚠️ Listín vacío o sin juegos")
            return None
        
        try:
            user_prompt = get_user_prompt(listin)
            
            logger.info(f"🧠 Enviando listín a Gemini ({len(listin['juegos'])} juegos)...")
            response = self.model.generate_content(user_prompt)
            
            if not response.text:
                logger.error("❌ Gemini retornó respuesta vacía")
                return None
            
            # Parsear JSON
            try:
                analisis = json.loads(response.text)
                logger.info("✅ Análisis de Gemini recibido y parseado")
                return analisis
            except json.JSONDecodeError as e:
                logger.error(f"❌ Error parseando JSON de Gemini: {e}")
                logger.debug(f"Respuesta cruda: {response.text[:500]}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error en Gemini: {e}")
            return None
    
    def guardar_picks(self, analisis: Dict, target_date: date = None) -> int:
        """Guarda los picks generados por el agente en la DB"""
        if not analisis:
            return 0
        
        if target_date is None:
            target_date = date.today()
        
        fecha_str = target_date.isoformat()
        guardados = 0
        
        # Directa del día
        if analisis.get("directa_del_dia"):
            try:
                db.insert("picks_diarios", {
                    "fecha": fecha_str,
                    "tipo_pick": "directa",
                    "juegos": [analisis["directa_del_dia"]],
                    "cuota_total": analisis["directa_del_dia"].get("cuota"),
                    "razonamiento": analisis["directa_del_dia"].get("razonamiento"),
                })
                guardados += 1
            except Exception as e:
                logger.error(f"❌ Error guardando directa: {e}")
        
        # Combinación principal
        if analisis.get("combinacion_principal"):
            try:
                comb = analisis["combinacion_principal"]
                db.insert("picks_diarios", {
                    "fecha": fecha_str,
                    "tipo_pick": "combinacion_1",
                    "juegos": comb.get("juegos", []),
                    "cuota_total": comb.get("cuota_total"),
                    "razonamiento": comb.get("nombre", ""),
                })
                guardados += 1
            except Exception as e:
                logger.error(f"❌ Error guardando combinación 1: {e}")
        
        # Combinación secundaria
        if analisis.get("combinacion_secundaria"):
            try:
                comb = analisis["combinacion_secundaria"]
                db.insert("picks_diarios", {
                    "fecha": fecha_str,
                    "tipo_pick": "combinacion_2",
                    "juegos": comb.get("juegos", []),
                    "cuota_total": comb.get("cuota_total"),
                    "razonamiento": comb.get("nombre", ""),
                })
                guardados += 1
            except Exception as e:
                logger.error(f"❌ Error guardando combinación 2: {e}")
        
        logger.info(f"💾 {guardados} picks guardados en DB")
        return guardados
    
    def ejecutar_analisis_completo(self, target_date: date = None) -> Optional[Dict]:
        """
        Pipeline completo: genera listín + analiza con Gemini + guarda picks.
        """
        if target_date is None:
            target_date = date.today()
        
        # 1. Generar listín JSON
        builder = ListinJSONBuilder()
        listin = builder.build(target_date)
        
        if not listin:
            logger.error("❌ No se pudo generar listín")
            return None
        
        # 2. Analizar con Gemini
        analisis = self.analizar_listin(listin)
        
        if not analisis:
            logger.error("❌ Gemini no generó análisis")
            return None
        
        # 3. Guardar picks
        self.guardar_picks(analisis, target_date)
        
        # 4. Guardar análisis completo en disco
        builder.output_dir.mkdir(parents=True, exist_ok=True)
        analisis_path = builder.output_dir / f"analisis_{target_date.isoformat()}.json"
        with open(analisis_path, "w", encoding="utf-8") as f:
            json.dump(analisis, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"💾 Análisis guardado en: {analisis_path}")
        
        return analisis


def run(target_date: date = None):
    """Ejecuta el agente completo"""
    agent = GeminiAgent()
    return agent.ejecutar_analisis_completo(target_date)


if __name__ == "__main__":
    run()
