"""
PicksProMLB - Motor de Filtros
Aplica los 10 filtros estadísticos a cada juego del día
"""

from typing import Dict, List, Tuple, Optional
from datetime import date
from loguru import logger
from app.utils.config import config
from app.utils.database import db


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
        """
        Aplica los 10 filtros y retorna cuáles pasa el equipo favorecido.
        """
        resultados = {}
        total_pasados = 0
        
        for filtro_id, filtro_def in self.filtros.items():
            try:
                pasa = filtro_def["condicion"](equipo, rival)
                resultados[filtro_id.lower()] = bool(pasa)
                if pasa:
                    total_pasados += 1
            except (KeyError, TypeError) as e:
                # Si falta algún campo, marcar como False
                resultados[filtro_id.lower()] = False
                logger.debug(f"⚠️ Filtro {filtro_id} no aplicable: {e}")
        
        resultados["total_filtros_pasados"] = total_pasados
        return resultados
    
    def detectar_zonas(self, equipo: Dict) -> Dict:
        """
        Detecta si un equipo está en zona de rebote técnico o caliente.
        Retorna las zonas detectadas.
        """
        zonas_detectadas = []
        
        # AVG bajo (rebote)
        if equipo.get("avg_l5") and equipo["avg_l5"] < 0.150:
            zonas_detectadas.append({
                "tipo": "rebote",
                "metrica": "AVG L5",
                "valor": equipo["avg_l5"],
                "descripcion": f"AVG L5 = {equipo['avg_l5']:.3f} (zona de rebote, 77% hace 3+ carreras)"
            })
        
        # AVG alto (caliente)
        if equipo.get("avg_l5") and equipo["avg_l5"] > 0.350:
            zonas_detectadas.append({
                "tipo": "caliente",
                "metrica": "AVG L5",
                "valor": equipo["avg_l5"],
                "descripcion": f"AVG L5 = {equipo['avg_l5']:.3f} (zona caliente, 100% hace 3+ carreras)"
            })
        
        # OBP alto
        if equipo.get("obp_l5") and equipo["obp_l5"] > 0.400:
            zonas_detectadas.append({
                "tipo": "caliente",
                "metrica": "OBP L5",
                "valor": equipo["obp_l5"],
                "descripcion": f"OBP L5 = {equipo['obp_l5']:.3f} (82% hace 3+ carreras)"
            })
        
        # SLG bajo (rebote)
        if equipo.get("slg_l5") and equipo["slg_l5"] < 0.300:
            zonas_detectadas.append({
                "tipo": "rebote",
                "metrica": "SLG L5",
                "valor": equipo["slg_l5"],
                "descripcion": f"SLG L5 = {equipo['slg_l5']:.3f} (zona de rebote, 70% hace 3+ carreras)"
            })
        
        # SLG alto
        if equipo.get("slg_l5") and equipo["slg_l5"] > 0.600:
            zonas_detectadas.append({
                "tipo": "caliente",
                "metrica": "SLG L5",
                "valor": equipo["slg_l5"],
                "descripcion": f"SLG L5 = {equipo['slg_l5']:.3f} (100% hace 3+ carreras)"
            })
        
        # ISO alto
        if equipo.get("iso_l5") and equipo["iso_l5"] > 0.250:
            zonas_detectadas.append({
                "tipo": "caliente",
                "metrica": "ISO L5",
                "valor": equipo["iso_l5"],
                "descripcion": f"ISO L5 = {equipo['iso_l5']:.3f} (73% hace 3+, 41% hace 5+)"
            })
        
        # BABIP alto
        if equipo.get("babip_l5") and equipo["babip_l5"] > 0.400:
            zonas_detectadas.append({
                "tipo": "caliente",
                "metrica": "BABIP L5",
                "valor": equipo["babip_l5"],
                "descripcion": f"BABIP L5 = {equipo['babip_l5']:.3f} (87.5% hace 3+ carreras)"
            })
        
        # wOBA alto
        if equipo.get("woba_l5") and equipo["woba_l5"] > 0.400:
            zonas_detectadas.append({
                "tipo": "caliente",
                "metrica": "wOBA L5",
                "valor": equipo["woba_l5"],
                "descripcion": f"wOBA L5 = {equipo['woba_l5']:.3f} (78% hace 3+ carreras)"
            })
        
        # wRC+ bajo (rebote)
        if equipo.get("wrc_plus_l5") and equipo["wrc_plus_l5"] < 50:
            zonas_detectadas.append({
                "tipo": "rebote",
                "metrica": "wRC+ L5",
                "valor": equipo["wrc_plus_l5"],
                "descripcion": f"wRC+ L5 = {equipo['wrc_plus_l5']} (zona de rebote, 77% hace 3+ carreras)"
            })
        
        # wRC+ alto
        if equipo.get("wrc_plus_l5") and equipo["wrc_plus_l5"] > 140:
            zonas_detectadas.append({
                "tipo": "caliente",
                "metrica": "wRC+ L5",
                "valor": equipo["wrc_plus_l5"],
                "descripcion": f"wRC+ L5 = {equipo['wrc_plus_l5']} (71% hace 3+, 51% hace 5+)"
            })
        
        return {
            "tiene_rebote": any(z["tipo"] == "rebote" for z in zonas_detectadas),
            "tiene_caliente": any(z["tipo"] == "caliente" for z in zonas_detectadas),
            "zonas": zonas_detectadas,
        }
    
    def detectar_alertas(self, equipo: Dict, rival: Dict, juego: Dict, bullpen_eq: Dict, bullpen_riv: Dict) -> List[str]:
        """Detecta alertas importantes (Coors, bullpen explotado, clima, etc.)"""
        alertas = []
        
        # Alerta Coors Field
        if equipo.get("jugo_en_coors"):
            alertas.append("⚠️ Equipo viene de Coors Field - números ofensivos pueden estar inflados")
        if rival.get("jugo_en_coors"):
            alertas.append("⚠️ Rival viene de Coors Field - números ofensivos pueden estar inflados")
        
        # Bullpen explotado (ERA > 6 en últimos 5)
        if bullpen_eq and bullpen_eq.get("era_l5", 0) > 6:
            alertas.append(f"⚠️ Bullpen propio con ERA L5 = {bullpen_eq['era_l5']:.2f} (explotado)")
        if bullpen_riv and bullpen_riv.get("era_l5", 0) > 6:
            alertas.append(f"✅ Bullpen rival con ERA L5 = {bullpen_riv['era_l5']:.2f} (explotado, ventaja)")
        
        # Clima
        if juego:
            temp_c = juego.get("clima_temp_c")
            humedad = juego.get("clima_humedad")
            lluvia = juego.get("clima_lluvia_pct", 0)
            
            if temp_c is not None and temp_c < 10:
                alertas.append(f"❄️ Clima frío ({temp_c}°C) - favorece bajas")
            
            if temp_c is not None and temp_c > 27 and humedad and humedad < 30:
                alertas.append(f"☀️ Clima caluroso y seco ({temp_c}°C, {humedad}% humedad) - favorece altas")
            
            if humedad and humedad > 80:
                alertas.append(f"💧 Humedad alta ({humedad}%) - favorece bajas (pelota pesada)")
            
            if lluvia > 30:
                alertas.append(f"🌧️ Probabilidad de lluvia: {lluvia}% - posible suspensión")
            
            # Estadio especial
            estadio = juego.get("estadio", "")
            if "Coors" in estadio:
                alertas.append("🏔️ Coors Field - altitud favorece altas (pelota viaja 15-21 pies más)")
            elif "Oracle" in estadio:
                alertas.append("🌫️ Oracle Park - humedad y dimensiones suprimen poder")
        
        return alertas
    
    def determinar_pick_y_mercado(
        self, 
        total_filtros: int, 
        cuota_ml: int, 
        zonas_rival: Dict,
        alertas: List[str]
    ) -> Dict:
        """
        Determina el pick recomendado y el mejor mercado según las reglas del tipster:
        - 8+ filtros = directa del día (ML)
        - 6-7 filtros = combinación principal
        - 4-5 filtros = solo run line/colchón
        - 0-3 filtros = no bet
        """
        if total_filtros >= config.UMBRAL_DIRECTA:
            # Si la cuota está cara (-180+), preferir RL
            if cuota_ml and cuota_ml < -180:
                return {
                    "pick": "Run Line +1.5",
                    "mercado": "RL +1.5",
                    "confianza": "alta",
                    "razon": f"{total_filtros}/10 filtros pero ML caro ({cuota_ml})"
                }
            return {
                "pick": "Moneyline",
                "mercado": "ML",
                "confianza": "alta",
                "razon": f"{total_filtros}/10 filtros - directa del día"
            }
        
        elif total_filtros >= config.UMBRAL_COMBINACION:
            return {
                "pick": "Moneyline",
                "mercado": "ML para combinación",
                "confianza": "media",
                "razon": f"{total_filtros}/10 filtros - candidato a combinación"
            }
        
        elif total_filtros >= config.UMBRAL_COLCHON:
            return {
                "pick": "Run Line +1.5",
                "mercado": "RL +1.5",
                "confianza": "baja",
                "razon": f"{total_filtros}/10 filtros - solo con colchón"
            }
        
        else:
            # Verificar si hay rebote técnico aprovechable
            if zonas_rival.get("tiene_rebote"):
                return {
                    "pick": "Rival más de 2.5 carreras",
                    "mercado": "Team Total Over",
                    "confianza": "media",
                    "razon": "Rival en zona de rebote técnico"
                }
            
            return {
                "pick": "NO BET",
                "mercado": None,
                "confianza": "no_bet",
                "razon": f"Solo {total_filtros}/10 filtros - no hay edge claro"
            }
    
    def analizar_juego(self, juego: Dict) -> Dict:
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
        
        # Obtener bullpenes
        bp_local = db.select("bullpenes_diario", filters={"fecha": fecha, "equipo": local})
        bp_visit = db.select("bullpenes_diario", filters={"fecha": fecha, "equipo": visitante})
        bp_local = bp_local[0] if bp_local else {}
        bp_visit = bp_visit[0] if bp_visit else {}
        
        # Determinar quién es el "favorecido" estadísticamente
        # (el equipo con mejor wRC+ L5 generalmente)
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
        
        # Calcular diferenciales
        diferenciales = self.calcular_diferenciales(equipo_fav, equipo_riv)
        
        # Detectar zonas
        zonas_fav = self.detectar_zonas(equipo_fav)
        zonas_riv = self.detectar_zonas(equipo_riv)
        
        # Detectar alertas
        alertas = self.detectar_alertas(equipo_fav, equipo_riv, juego, bp_fav, bp_riv)
        
        # Determinar pick
        pick_info = self.determinar_pick_y_mercado(
            filtros_resultado["total_filtros_pasados"],
            cuota_ml,
            zonas_riv,
            alertas
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
            "nivel_confianza": pick_info["confianza"],
        }
        
        return analisis
    
    def analizar_dia(self, target_date: date = None) -> List[Dict]:
        """
        Analiza TODOS los juegos de un día y guarda los resultados.
        """
        if target_date is None:
            target_date = date.today()
        
        fecha_str = target_date.isoformat()
        
        # Obtener todos los juegos del día
        juegos = db.select("juegos", filters={"fecha": fecha_str})
        
        if not juegos:
            logger.warning(f"⚠️ No hay juegos para {fecha_str}")
            return []
        
        analisis_dia = []
        for juego in juegos:
            try:
                analisis = self.analizar_juego(juego)
                if analisis:
                    # Guardar en DB
                    db.upsert(
                        "filtros_aplicados",
                        analisis,
                        on_conflict="fecha,equipo_favorecido,equipo_rival"
                    )
                    analisis_dia.append(analisis)
                    
                    logger.info(
                        f"✅ {analisis['equipo_favorecido']} vs {analisis['equipo_rival']}: "
                        f"{analisis['total_filtros_pasados']}/10 filtros - {analisis['pick_recomendado']}"
                    )
            except Exception as e:
                logger.error(f"❌ Error analizando {juego.get('equipo_local')} vs {juego.get('equipo_visitante')}: {e}")
        
        logger.info(f"🎯 Análisis completado: {len(analisis_dia)} juegos analizados")
        return analisis_dia


def run(target_date: date = None):
    """Ejecuta el motor de filtros para un día"""
    engine = FilterEngine()
    return engine.analizar_dia(target_date)


if __name__ == "__main__":
    run()
