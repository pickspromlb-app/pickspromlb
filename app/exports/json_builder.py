"""
PicksProMLB - Generador de JSON del listín
Crea el JSON limpio que el agente Gemini usará para análisis
"""

import json
from datetime import date, datetime
from typing import Dict, List
from pathlib import Path
from loguru import logger
from app.utils.database import db
from app.utils.config import config


class ListinJSONBuilder:
    """Construye el JSON del listín diario"""
    
    def __init__(self):
        self.output_dir = Path("data/listines")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def build(self, target_date: date = None) -> Dict:
        """Construye el JSON completo del día"""
        if target_date is None:
            target_date = date.today()
        
        fecha_str = target_date.isoformat()
        
        # Obtener todos los juegos del día
        juegos = db.select("juegos", filters={"fecha": fecha_str})
        if not juegos:
            logger.warning(f"⚠️ No hay juegos para {fecha_str}")
            return None
        
        # Obtener análisis de filtros
        filtros = db.select("filtros_aplicados", filters={"fecha": fecha_str})
        filtros_map = {(f["equipo_favorecido"], f["equipo_rival"]): f for f in filtros}
        
        # Construir JSON por juego
        juegos_json = []
        for juego in juegos:
            local = juego["equipo_local"]
            visit = juego["equipo_visitante"]
            
            # Buscar análisis (puede estar en cualquier dirección)
            analisis = filtros_map.get((local, visit)) or filtros_map.get((visit, local))
            
            # Stats de equipos
            stats_local = db.select("equipos_diario", filters={"fecha": fecha_str, "equipo": local})
            stats_visit = db.select("equipos_diario", filters={"fecha": fecha_str, "equipo": visit})
            
            stats_local = stats_local[0] if stats_local else {}
            stats_visit = stats_visit[0] if stats_visit else {}
            
            # Bullpenes
            bp_local = db.select("bullpenes_diario", filters={"fecha": fecha_str, "equipo": local})
            bp_visit = db.select("bullpenes_diario", filters={"fecha": fecha_str, "equipo": visit})
            bp_local = bp_local[0] if bp_local else {}
            bp_visit = bp_visit[0] if bp_visit else {}
            
            juego_completo = {
                "fecha": fecha_str,
                "hora_inicio": juego.get("hora_inicio"),
                "estadio": juego.get("estadio"),
                "matchup": f"{visit} @ {local}",
                "equipos": {
                    "local": {
                        "abreviacion": local,
                        "nombre": config.EQUIPOS_MLB.get(local, local),
                        "stats": self._extraer_stats(stats_local),
                        "bullpen": self._extraer_bullpen(bp_local),
                    },
                    "visitante": {
                        "abreviacion": visit,
                        "nombre": config.EQUIPOS_MLB.get(visit, visit),
                        "stats": self._extraer_stats(stats_visit),
                        "bullpen": self._extraer_bullpen(bp_visit),
                    },
                },
                "pitchers": {
                    "local": juego.get("pitcher_local"),
                    "visitante": juego.get("pitcher_visitante"),
                },
                "mercado": {
                    "ml_local": juego.get("ml_local"),
                    "ml_visitante": juego.get("ml_visitante"),
                    "rl_local": juego.get("rl_local"),
                    "rl_visitante": juego.get("rl_visitante"),
                    "rl_local_odds": juego.get("rl_local_odds"),
                    "rl_visitante_odds": juego.get("rl_visitante_odds"),
                    "total": juego.get("total_runs"),
                },
                "clima": {
                    "temp_c": juego.get("clima_temp_c"),
                    "temp_f": juego.get("clima_temp_f"),
                    "humedad": juego.get("clima_humedad"),
                    "viento_mph": juego.get("clima_viento_mph"),
                    "viento_dir": juego.get("clima_viento_direccion"),
                    "lluvia_pct": juego.get("clima_lluvia_pct"),
                },
                "analisis": self._formatear_analisis(analisis) if analisis else None,
            }
            
            juegos_json.append(juego_completo)
        
        # Construir JSON final
        listin = {
            "metadata": {
                "fecha": fecha_str,
                "generado_en": datetime.now().isoformat(),
                "total_juegos": len(juegos_json),
                "juegos_con_analisis": len([j for j in juegos_json if j["analisis"]]),
                "version": "1.0",
            },
            "resumen": self._construir_resumen(juegos_json),
            "juegos": juegos_json,
        }
        
        return listin
    
    def _extraer_stats(self, stats: Dict) -> Dict:
        """Extrae solo las stats relevantes para el listín"""
        return {
            "temporada": {
                "avg": stats.get("avg_temp"),
                "obp": stats.get("obp_temp"),
                "slg": stats.get("slg_temp"),
                "ops": stats.get("ops_temp"),
                "iso": stats.get("iso_temp"),
                "babip": stats.get("babip_temp"),
                "woba": stats.get("woba_temp"),
                "wrc_plus": stats.get("wrc_plus_temp"),
                "wraa": stats.get("wraa_temp"),
                "bb_pct": stats.get("bb_pct_temp"),
                "k_pct": stats.get("k_pct_temp"),
                "bbk": stats.get("bbk_temp"),
            },
            "ventanas": {
                "L10": {
                    "ops": stats.get("ops_l10"),
                    "iso": stats.get("iso_l10"),
                    "babip": stats.get("babip_l10"),
                    "wraa": stats.get("wraa_l10"),
                    "woba": stats.get("woba_l10"),
                    "wrc_plus": stats.get("wrc_plus_l10"),
                },
                "L7": {
                    "ops": stats.get("ops_l7"),
                    "iso": stats.get("iso_l7"),
                    "babip": stats.get("babip_l7"),
                    "wraa": stats.get("wraa_l7"),
                    "woba": stats.get("woba_l7"),
                    "wrc_plus": stats.get("wrc_plus_l7"),
                },
                "L5": {
                    "avg": stats.get("avg_l5"),
                    "obp": stats.get("obp_l5"),
                    "slg": stats.get("slg_l5"),
                    "ops": stats.get("ops_l5"),
                    "iso": stats.get("iso_l5"),
                    "babip": stats.get("babip_l5"),
                    "wraa": stats.get("wraa_l5"),
                    "woba": stats.get("woba_l5"),
                    "wrc_plus": stats.get("wrc_plus_l5"),
                    "bb_pct": stats.get("bb_pct_l5"),
                    "k_pct": stats.get("k_pct_l5"),
                    "bbk": stats.get("bbk_l5"),
                },
                "L3": {
                    "ops": stats.get("ops_l3"),
                    "iso": stats.get("iso_l3"),
                    "babip": stats.get("babip_l3"),
                    "wraa": stats.get("wraa_l3"),
                    "woba": stats.get("woba_l3"),
                    "wrc_plus": stats.get("wrc_plus_l3"),
                },
                "L1": {
                    "ops": stats.get("ops_l1"),
                    "iso": stats.get("iso_l1"),
                    "babip": stats.get("babip_l1"),
                    "wraa": stats.get("wraa_l1"),
                    "woba": stats.get("woba_l1"),
                    "wrc_plus": stats.get("wrc_plus_l1"),
                },
            },
            "viene_de_coors": stats.get("jugo_en_coors", False),
        }
    
    def _extraer_bullpen(self, bp: Dict) -> Dict:
        """Extrae stats del bullpen"""
        if not bp:
            return None
        return {
            "era_l5": bp.get("era_l5"),
            "fip_l5": bp.get("fip_l5"),
            "xfip_l5": bp.get("xfip_l5"),
            "whip_l5": bp.get("whip_l5"),
            "avg_permitido_l5": bp.get("avg_permitido_l5"),
            "k_pct_l5": bp.get("k_pct_l5"),
            "bb_pct_l5": bp.get("bb_pct_l5"),
            "hr_9_l5": bp.get("hr_9_l5"),
        }
    
    def _formatear_analisis(self, analisis: Dict) -> Dict:
        """Formatea el análisis para el JSON"""
        filtros_pasados = []
        for i in range(1, 11):
            if analisis.get(f"f{i}"):
                filtros_pasados.append(f"F{i}")
        
        return {
            "favorito_estadistico": analisis["equipo_favorecido"],
            "rival": analisis["equipo_rival"],
            "total_filtros": analisis["total_filtros_pasados"],
            "filtros_pasados": filtros_pasados,
            "diferenciales": {
                "woba_diff": analisis.get("woba_diff"),
                "wrc_plus_diff": analisis.get("wrc_plus_diff"),
                "ops_diff": analisis.get("ops_diff"),
                "wraa_diff": analisis.get("wraa_diff"),
                "bbk_diff": analisis.get("bbk_diff"),
            },
            "alertas": analisis.get("alertas", []),
            "rebote_tecnico_rival": analisis.get("rebote_tecnico_rival", False),
            "rival_caliente": analisis.get("rival_zona_caliente", False),
            "pick_recomendado": analisis.get("pick_recomendado"),
            "mercado_recomendado": analisis.get("mercado_recomendado"),
            "nivel_confianza": analisis.get("nivel_confianza"),
        }
    
    def _construir_resumen(self, juegos: List[Dict]) -> Dict:
        """Construye un resumen ejecutivo del día"""
        directas = []
        combinaciones = []
        colchones = []
        no_bets = []
        
        for j in juegos:
            if not j.get("analisis"):
                continue
            
            analisis = j["analisis"]
            confianza = analisis.get("nivel_confianza")
            
            item = {
                "matchup": j["matchup"],
                "favorito": analisis["favorito_estadistico"],
                "filtros": analisis["total_filtros"],
                "pick": analisis["pick_recomendado"],
                "mercado": analisis["mercado_recomendado"],
            }
            
            if confianza == "alta":
                directas.append(item)
            elif confianza == "media":
                combinaciones.append(item)
            elif confianza == "baja":
                colchones.append(item)
            else:
                no_bets.append(item)
        
        # Ordenar por filtros descendente
        directas.sort(key=lambda x: x["filtros"], reverse=True)
        combinaciones.sort(key=lambda x: x["filtros"], reverse=True)
        
        return {
            "directas_del_dia": directas,
            "candidatos_combinacion": combinaciones,
            "candidatos_colchon": colchones,
            "no_bets": no_bets,
            "estadisticas": {
                "total_directas": len(directas),
                "total_combinaciones": len(combinaciones),
                "total_colchones": len(colchones),
                "total_no_bets": len(no_bets),
            }
        }
    
    def save(self, listin: Dict, target_date: date = None) -> Path:
        """Guarda el JSON en disco"""
        if target_date is None:
            target_date = date.today()
        
        filename = f"listin_{target_date.isoformat()}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(listin, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"💾 Listín guardado en: {filepath}")
        return filepath


def run(target_date: date = None):
    """Genera el JSON del listín del día"""
    builder = ListinJSONBuilder()
    listin = builder.build(target_date)
    if listin:
        builder.save(listin, target_date)
    return listin


if __name__ == "__main__":
    run()
