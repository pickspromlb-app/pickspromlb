"""
PicksProMLB - Motor de Filtros (v2.1)
==========================================================
Aplica los 10 filtros estadísticos a cada juego del día.

CORRECCIONES v2.1:
- Usa get_today_et() en lugar de date.today() (FIX TZ)
- Genera tipos de pick ESTANDARIZADOS compatibles con pick_evaluator:
    "ML", "RL+1.5", "RL+2.5", "TEAM_OVER_2.5", "OVER_8.5", "UNDER_7.5"
- SIEMPRE incluye el campo "equipo_pick" para que el evaluador sepa qué evaluar
- Incluye "linea_pick" cuando aplica (RL, totales)
"""

from typing import Dict, List, Tuple, Optional
from datetime import date
from loguru import logger

from app.utils.config import config
from app.utils.database import db
from app.utils.time_utils import get_today_et


class FilterEngine:
    """Motor que aplica los 10 filtros a cada juego del día"""

    def __init__(self):
        self.filtros = config.FILTROS
        self.zonas_rebote = config.ZONAS_REBOTE

    def calcular_diferenciales(self, equipo: Dict, rival: Dict) -> Dict:
        """Calcula los diferenciales estadísticos entre dos equipos"""
        return {
            "woba_diff": round(equipo.get("woba_l5", 0) - rival.get("woba_l5", 0), 4),
            "wrc_plus_diff": (equipo.get("wrc_plus_l5", 0) or 0) - (rival.get("wrc_plus_l5", 0) or 0),
            "ops_diff": round(equipo.get("ops_l5", 0) - rival.get("ops_l5", 0), 4),
            "wraa_diff": round(equipo.get("wraa_l5", 0) - rival.get("wraa_l5", 0), 2),
            "bbk_diff": round(equipo.get("bbk_l5", 0) - rival.get("bbk_l5", 0), 2),
            "iso_diff": round(equipo.get("iso_l5", 0) - rival.get("iso_l5", 0), 4),
            "babip_diff": round(equipo.get("babip_l5", 0) - rival.get("babip_l5", 0), 4),
        }

    def aplicar_filtros(self, equipo: Dict, rival: Dict) -> Dict:
        """Aplica los 10 filtros y retorna cuáles pasa el equipo favorecido."""
        resultados = {}
        total_pasados = 0

        for filtro_id, filtro_def in self.filtros.items():
            try:
                pasa = filtro_def["condicion"](equipo, rival)
                resultados[filtro_id.lower()] = bool(pasa)
                if pasa:
                    total_pasados += 1
            except (KeyError, TypeError) as e:
                resultados[filtro_id.lower()] = False
                logger.debug(f"⚠️ Filtro {filtro_id} no aplicable: {e}")

        resultados["total_filtros_pasados"] = total_pasados
        return resultados

    def detectar_zonas(self, equipo: Dict) -> Dict:
        """Detecta si un equipo está en zona de rebote técnico o caliente."""
        zonas_detectadas = []

        if equipo.get("avg_l5") and equipo["avg_l5"] < 0.150:
            zonas_detectadas.append({
                "tipo": "rebote", "metrica": "AVG L5", "valor": equipo["avg_l5"],
                "descripcion": f"AVG L5 = {equipo['avg_l5']:.3f} (zona de rebote, 77% hace 3+ carreras)"
            })
        if equipo.get("avg_l5") and equipo["avg_l5"] > 0.350:
            zonas_detectadas.append({
                "tipo": "caliente", "metrica": "AVG L5", "valor": equipo["avg_l5"],
                "descripcion": f"AVG L5 = {equipo['avg_l5']:.3f} (zona caliente, 100% hace 3+ carreras)"
            })
        if equipo.get("obp_l5") and equipo["obp_l5"] > 0.400:
            zonas_detectadas.append({
                "tipo": "caliente", "metrica": "OBP L5", "valor": equipo["obp_l5"],
                "descripcion": f"OBP L5 = {equipo['obp_l5']:.3f} (82% hace 3+ carreras)"
            })
        if equipo.get("slg_l5") and equipo["slg_l5"] < 0.300:
            zonas_detectadas.append({
                "tipo": "rebote", "metrica": "SLG L5", "valor": equipo["slg_l5"],
                "descripcion": f"SLG L5 = {equipo['slg_l5']:.3f} (zona de rebote, 70% hace 3+ carreras)"
            })
        if equipo.get("slg_l5") and equipo["slg_l5"] > 0.600:
            zonas_detectadas.append({
                "tipo": "caliente", "metrica": "SLG L5", "valor": equipo["slg_l5"],
                "descripcion": f"SLG L5 = {equipo['slg_l5']:.3f} (100% hace 3+ carreras)"
            })
        if equipo.get("iso_l5") and equipo["iso_l5"] > 0.250:
            zonas_detectadas.append({
                "tipo": "caliente", "metrica": "ISO L5", "valor": equipo["iso_l5"],
                "descripcion": f"ISO L5 = {equipo['iso_l5']:.3f} (73% hace 3+, 41% hace 5+)"
            })
        if equipo.get("babip_l5") and equipo["babip_l5"] > 0.400:
            zonas_detectadas.append({
                "tipo": "caliente", "metrica": "BABIP L5", "valor": equipo["babip_l5"],
                "descripcion": f"BABIP L5 = {equipo['babip_l5']:.3f} (87.5% hace 3+ carreras)"
            })
        if equipo.get("woba_l5") and equipo["woba_l5"] > 0.400:
            zonas_detectadas.append({
                "tipo": "caliente", "metrica": "wOBA L5", "valor": equipo["woba_l5"],
                "descripcion": f"wOBA L5 = {equipo['woba_l5']:.3f} (78% hace 3+ carreras)"
            })
        if equipo.get("wrc_plus_l5") and equipo["wrc_plus_l5"] < 50:
            zonas_detectadas.append({
                "tipo": "rebote", "metrica": "wRC+ L5", "valor": equipo["wrc_plus_l5"],
                "descripcion": f"wRC+ L5 = {equipo['wrc_plus_l5']} (zona de rebote, 77% hace 3+ carreras)"
            })
        if equipo.get("wrc_plus_l5") and equipo["wrc_plus_l5"] > 140:
            zonas_detectadas.append({
                "tipo": "caliente", "metrica": "wRC+ L5", "valor": equipo["wrc_plus_l5"],
                "descripcion": f"wRC+ L5 = {equipo['wrc_plus_l5']} (71% hace 3+, 51% hace 5+)"
            })

        return {
            "tiene_rebote": any(z["tipo"] == "rebote" for z in zonas_detectadas),
            "tiene_caliente": any(z["tipo"] == "caliente" for z in zonas_detectadas),
            "zonas": zonas_detectadas,
        }

    def detectar_alertas(
        self, equipo: Dict, rival: Dict, juego: Dict, bullpen_eq: Dict, bullpen_riv: Dict
    ) -> List[str]:
        """Detecta alertas importantes (Coors, bullpen explotado, clima, etc.)"""
        alertas = []

        if equipo.get("jugo_en_coors"):
            alertas.append("⚠️ Equipo viene de Coors Field - números ofensivos pueden estar inflados")
        if rival.get("jugo_en_coors"):
            alertas.append("⚠️ Rival viene de Coors Field - números ofensivos pueden estar inflados")

        if bullpen_eq and bullpen_eq.get("era_l5", 0) > 6:
            alertas.append(f"⚠️ Bullpen propio con ERA L5 = {bullpen_eq['era_l5']:.2f} (explotado)")
        if bullpen_riv and bullpen_riv.get("era_l5", 0) > 6:
            alertas.append(f"✅ Bullpen rival con ERA L5 = {bullpen_riv['era_l5']:.2f} (explotado, ventaja)")

        if juego:
            temp_c = juego.get("clima_temp_c")
            humedad = juego.get("clima_humedad")
            lluvia = juego.get("clima_lluvia_pct", 0)
            estadio = juego.get("estadio", "")

            if temp_c is not None and temp_c < 10:
                alertas.append(f"❄️ Clima frío ({temp_c}°C) - favorece bajas")
            if temp_c is not None and temp_c > 27 and humedad and humedad < 30:
                alertas.append(f"☀️ Clima caluroso y seco ({temp_c}°C, {humedad}% humedad) - favorece altas")
            if humedad and humedad > 80:
                alertas.append(f"💧 Humedad alta ({humedad}%) - favorece bajas (pelota pesada)")
            if lluvia and lluvia > 30:
                alertas.append(f"🌧️ Probabilidad de lluvia: {lluvia}% - posible suspensión")

            if "Coors" in estadio:
                alertas.append("🏔️ Coors Field - altitud favorece altas (pelota viaja 15-21 pies más)")
            elif "Oracle" in estadio:
                alertas.append("🌫️ Oracle Park - humedad y dimensiones suprimen poder")

        return alertas

    def determinar_pick_y_mercado(
        self,
        total_filtros: int,
        cuota_ml: Optional[int],
        zonas_rival: Dict,
        alertas: List[str],
        equipo_favorito: str,
        equipo_rival: str,
    ) -> Dict:
        """
        Determina el pick recomendado.
        IMPORTANTE: Genera tipos de pick ESTANDARIZADOS compatibles con pick_evaluator:
            "ML", "RL+1.5", "RL+2.5", "TEAM_OVER_2.5", "OVER_8.5", etc.
        Y SIEMPRE incluye:
            - equipo_pick (qué equipo es)
            - linea_pick (la línea numérica si aplica)
        """
        # Reglas según el tipster:
        # - 8+ filtros = directa del día (ML)
        # - 6-7 filtros = combinación principal
        # - 4-5 filtros = solo run line/colchón
        # - 0-3 filtros = no bet (o ver rebote)

        if total_filtros >= config.UMBRAL_DIRECTA:  # 8+
            # Si la cuota está cara (ML < -180), preferir RL +1.5
            if cuota_ml and cuota_ml < -180:
                return {
                    "pick": f"{equipo_favorito} Run Line +1.5",
                    "mercado": "RL +1.5",
                    "tipo_pick": "RL+1.5",
                    "equipo_pick": equipo_favorito,
                    "linea_pick": 1.5,
                    "confianza": "alta",
                    "razon": f"{total_filtros}/10 filtros pero ML caro ({cuota_ml})",
                }
            return {
                "pick": f"{equipo_favorito} Moneyline",
                "mercado": "ML",
                "tipo_pick": "ML",
                "equipo_pick": equipo_favorito,
                "linea_pick": None,
                "confianza": "alta",
                "razon": f"{total_filtros}/10 filtros - directa del día",
            }

        elif total_filtros >= config.UMBRAL_COMBINACION:  # 6-7
            return {
                "pick": f"{equipo_favorito} Moneyline",
                "mercado": "ML para combinación",
                "tipo_pick": "ML",
                "equipo_pick": equipo_favorito,
                "linea_pick": None,
                "confianza": "media",
                "razon": f"{total_filtros}/10 filtros - candidato a combinación",
            }

        elif total_filtros >= config.UMBRAL_COLCHON:  # 4-5
            return {
                "pick": f"{equipo_favorito} Run Line +1.5",
                "mercado": "RL +1.5",
                "tipo_pick": "RL+1.5",
                "equipo_pick": equipo_favorito,
                "linea_pick": 1.5,
                "confianza": "baja",
                "razon": f"{total_filtros}/10 filtros - solo con colchón",
            }

        else:
            # Verificar si hay rebote técnico aprovechable en el rival
            if zonas_rival.get("tiene_rebote"):
                return {
                    "pick": f"{equipo_rival} más de 2.5 carreras",
                    "mercado": "Team Total Over 2.5",
                    "tipo_pick": "TEAM_OVER_2.5",
                    "equipo_pick": equipo_rival,
                    "linea_pick": 2.5,
                    "confianza": "media",
                    "razon": "Rival en zona de rebote técnico",
                }
            return {
                "pick": "NO BET",
                "mercado": None,
                "tipo_pick": None,
                "equipo_pick": None,
                "linea_pick": None,
                "confianza": "no_bet",
                "razon": f"Solo {total_filtros}/10 filtros - no hay edge claro",
            }

    def analizar_juego(self, juego: Dict) -> Optional[Dict]:
        """
        Analiza un juego completo aplicando todos los filtros y reglas.
        Retorna el análisis completo listo para guardar en DB.
        """
        fecha = juego["fecha"]
        local = juego["equipo_local"]
        visitante = juego["equipo_visitante"]

        # Obtener stats de ambos equipos
        stats_local = db.select("equipos_diario", filters={"fecha": fecha, "equipo": local})
        stats_visit = db.select("equipos_diario", filters={"fecha": fecha, "equipo": visitante})

        if not stats_local or not stats_visit:
            logger.warning(f"⚠️ Stats faltantes para {local} vs {visitante}")
            return None

        eq_local = stats_local[0]
        eq_visit = stats_visit[0]

        # Bullpenes
        bp_local = db.select("bullpenes_diario", filters={"fecha": fecha, "equipo": local})
        bp_visit = db.select("bullpenes_diario", filters={"fecha": fecha, "equipo": visitante})
        bp_local = bp_local[0] if bp_local else {}
        bp_visit = bp_visit[0] if bp_visit else {}

        # Determinar el favorecido estadísticamente (mejor wRC+ L5)
        if eq_local.get("wrc_plus_l5", 0) >= eq_visit.get("wrc_plus_l5", 0):
            equipo_fav = eq_local
            equipo_riv = eq_visit
            bp_fav = bp_local
            bp_riv = bp_visit
            fav_abbr = local
            riv_abbr = visitante
            cuota_ml = juego.get("ml_local")
        else:
            equipo_fav = eq_visit
            equipo_riv = eq_local
            bp_fav = bp_visit
            bp_riv = bp_local
            fav_abbr = visitante
            riv_abbr = local
            cuota_ml = juego.get("ml_visitante")

        # Aplicar filtros
        filtros_resultado = self.aplicar_filtros(equipo_fav, equipo_riv)

        # Diferenciales
        diferenciales = self.calcular_diferenciales(equipo_fav, equipo_riv)

        # Zonas
        zonas_fav = self.detectar_zonas(equipo_fav)
        zonas_riv = self.detectar_zonas(equipo_riv)

        # Alertas
        alertas = self.detectar_alertas(equipo_fav, equipo_riv, juego, bp_fav, bp_riv)

        # Pick (CON equipo y línea)
        pick_info = self.determinar_pick_y_mercado(
            filtros_resultado["total_filtros_pasados"],
            cuota_ml,
            zonas_riv,
            alertas,
            fav_abbr,
            riv_abbr,
        )

        # Construir resultado completo
        analisis = {
            "fecha": fecha,
            "juego_id": juego.get("id"),
            "equipo_favorecido": fav_abbr,
            "equipo_rival": riv_abbr,
            **filtros_resultado,
            **diferenciales,
            "alertas": alertas,
            "rebote_tecnico_rival": zonas_riv["tiene_rebote"],
            "rival_zona_caliente": zonas_riv["tiene_caliente"],
            "pick_recomendado": pick_info["pick"],
            "mercado_recomendado": pick_info["mercado"],
            "tipo_pick": pick_info["tipo_pick"],         # NUEVO: estandarizado
            "equipo_pick": pick_info["equipo_pick"],     # NUEVO: equipo del pick
            "linea_pick": pick_info["linea_pick"],       # NUEVO: línea si aplica
            "nivel_confianza": pick_info["confianza"],
        }

        return analisis

    def analizar_dia(self, target_date: date = None) -> List[Dict]:
        """Analiza TODOS los juegos de un día y guarda los resultados."""
        # FIX TZ: usar get_today_et()
        if target_date is None:
            target_date = get_today_et()

        fecha_str = target_date.isoformat()
        juegos = db.select("juegos", filters={"fecha": fecha_str})

        if not juegos:
            logger.warning(f"⚠️ No hay juegos para {fecha_str}")
            return []

        analisis_dia = []
        for juego in juegos:
            try:
                analisis = self.analizar_juego(juego)
                if analisis:
                    db.upsert(
                        "filtros_aplicados",
                        analisis,
                        on_conflict="fecha,equipo_favorecido,equipo_rival",
                    )
                    analisis_dia.append(analisis)
                    logger.info(
                        f"✅ {analisis['equipo_favorecido']} vs {analisis['equipo_rival']}: "
                        f"{analisis['total_filtros_pasados']}/10 filtros - {analisis['pick_recomendado']}"
                    )
            except Exception as e:
                logger.error(
                    f"❌ Error analizando {juego.get('equipo_local')} vs {juego.get('equipo_visitante')}: {e}"
                )

        logger.info(f"🎯 Análisis completado: {len(analisis_dia)} juegos analizados")
        return analisis_dia


def run(target_date: date = None):
    """Ejecuta el motor de filtros para un día"""
    engine = FilterEngine()
    return engine.analizar_dia(target_date)


if __name__ == "__main__":
    run()
