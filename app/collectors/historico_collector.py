"""
PicksProMLB - Collector con caché histórica de 20 días
================================================================
ARQUITECTURA INTELIGENTE:
1. cargar_inicial(20) → UNA SOLA VEZ: jala últimos 20 días de los 30 equipos (~30 min)
2. actualizar_ayer() → CADA MAÑANA: solo procesa juegos del día anterior (~5 min)
3. Las stats por ventana (L1-L10) se RECALCULAN desde la BD local (instantáneo)

Resultado: /analizar pasa de tardar 25 min a < 1 min.
"""

import statsapi
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger

from app.utils.database import db
from app.utils.config import config
from app.utils.time_utils import get_today_et, get_yesterday_et


# IDs de MLB para cada equipo
MLB_TEAM_IDS = {
    "ARI": 109, "ATL": 144, "BAL": 110, "BOS": 111, "CHC": 112,
    "CHW": 145, "CIN": 113, "CLE": 114, "COL": 115, "DET": 116,
    "HOU": 117, "KCR": 118, "LAA": 108, "LAD": 119, "MIA": 146,
    "MIL": 158, "MIN": 142, "NYM": 121, "NYY": 147, "ATH": 133,
    "PHI": 143, "PIT": 134, "SDP": 135, "SEA": 136, "SFG": 137,
    "STL": 138, "TBR": 139, "TEX": 140, "TOR": 141, "WSN": 120,
}

# Días de histórico que mantenemos (lo que pidió Antonio)
DIAS_HISTORICO = 20


class HistoricoCollector:
    """Collector con caché. La API solo se llama cuando es necesario."""

    def __init__(self):
        pass

    # ========================= EXTRACCIÓN DE BOXSCORE =========================

    def _extraer_stats_juego(self, game_id: int, team_id: int) -> Optional[Dict]:
        """
        Extrae bateo + bullpen de un equipo en un juego específico.
        Devuelve un dict con todas las stats brutas (no calculadas).
        """
        try:
            box = statsapi.boxscore_data(game_id)
        except Exception as e:
            logger.debug(f"No se pudo obtener boxscore {game_id}: {e}")
            return None

        # Determinar lado del equipo
        try:
            home_id = box.get("teamInfo", {}).get("home", {}).get("id")
            away_id = box.get("teamInfo", {}).get("away", {}).get("id")
            if home_id == team_id:
                side = "home"
            elif away_id == team_id:
                side = "away"
            else:
                return None
        except Exception:
            return None

        team_data = box.get(side, {})

        # ===== STATS DE BATEO =====
        batting = team_data.get("teamStats", {}).get("batting", {})
        if not batting:
            return None

        ab = int(batting.get("atBats", 0))
        bb = int(batting.get("baseOnBalls", 0))
        hbp = int(batting.get("hitByPitch", 0))
        sf = int(batting.get("sacFlies", 0))
        pa = int(batting.get("plateAppearances", 0)) or (ab + bb + hbp + sf)

        bateo = {
            "pa": pa,
            "ab": ab,
            "h": int(batting.get("hits", 0)),
            "doubles": int(batting.get("doubles", 0)),
            "triples": int(batting.get("triples", 0)),
            "hr": int(batting.get("homeRuns", 0)),
            "rbi": int(batting.get("rbi", 0)),
            "bb": bb,
            "so": int(batting.get("strikeOuts", 0)),
            "hbp": hbp,
            "sb": int(batting.get("stolenBases", 0)),
            "sf": sf,
            "tb": int(batting.get("totalBases", 0)),
            "lob": int(batting.get("leftOnBase", 0)),
            "r": int(batting.get("runs", 0)),
        }

        # ===== STATS DEL BULLPEN =====
        # Saltamos el primer pitcher (abridor) y agregamos el resto
        pitchers = team_data.get("pitchers", [])
        players = team_data.get("players", {})

        bullpen = {
            "bp_ip_outs": 0, "bp_h": 0, "bp_r": 0, "bp_er": 0,
            "bp_bb": 0, "bp_so": 0, "bp_hr": 0, "bp_hbp": 0, "bp_tbf": 0,
        }

        if len(pitchers) >= 2:
            for pid in pitchers[1:]:  # Saltamos abridor
                player_key = f"ID{pid}"
                player = players.get(player_key, {})
                pstats = player.get("stats", {}).get("pitching", {})
                if not pstats:
                    continue

                # IP viene como "1.2" (1 ip + 2 outs)
                ip_str = str(pstats.get("inningsPitched", "0.0"))
                try:
                    whole = int(float(ip_str))
                    fraction = round((float(ip_str) - whole) * 10)
                    outs = whole * 3 + fraction
                except (ValueError, TypeError):
                    outs = 0

                bullpen["bp_ip_outs"] += outs
                bullpen["bp_h"] += int(pstats.get("hits", 0))
                bullpen["bp_r"] += int(pstats.get("runs", 0))
                bullpen["bp_er"] += int(pstats.get("earnedRuns", 0))
                bullpen["bp_bb"] += int(pstats.get("baseOnBalls", 0))
                bullpen["bp_so"] += int(pstats.get("strikeOuts", 0))
                bullpen["bp_hr"] += int(pstats.get("homeRuns", 0))
                bullpen["bp_hbp"] += int(pstats.get("hitByPitch", 0))
                bullpen["bp_tbf"] += int(pstats.get("battersFaced", 0))

        return {**bateo, **bullpen}

    # ========================= OBTENER JUEGOS DE UN RANGO =========================

    def _obtener_juegos_equipo_rango(
        self, team_abbr: str, start: date, end: date
    ) -> List[Dict]:
        """Obtiene juegos finalizados de un equipo en rango de fechas"""
        team_id = MLB_TEAM_IDS.get(team_abbr)
        if not team_id:
            return []

        try:
            schedule = statsapi.schedule(
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
                team=team_id,
            )
        except Exception as e:
            logger.error(f"Error obteniendo schedule {team_abbr}: {e}")
            return []

        return [g for g in schedule if g.get("status") in ["Final", "Game Over"]]

    # ========================= PROCESAR Y GUARDAR =========================

    def _procesar_juego_equipo(
        self, team_abbr: str, juego: Dict
    ) -> Optional[Dict]:
        """Procesa un juego individual y lo prepara para guardar en BD"""
        team_id = MLB_TEAM_IDS.get(team_abbr)
        game_id = juego.get("game_id")
        game_date = juego.get("game_date")

        if not game_id or not game_date:
            return None

        stats = self._extraer_stats_juego(game_id, team_id)
        if not stats:
            return None

        return {
            "fecha_juego": game_date,
            "equipo": team_abbr,
            "estadio": juego.get("venue_name", ""),
            **stats,
        }

    def _ya_existe_en_bd(self, team_abbr: str, fecha: str) -> bool:
        """Verifica si un juego ya está guardado (para no duplicar trabajo)"""
        try:
            data = db.select(
                "historico_juegos_equipos",
                filters={"equipo": team_abbr, "fecha_juego": fecha},
            )
            return len(data) > 0
        except Exception:
            return False

    def _guardar_juego(self, registro: Dict) -> bool:
        """Guarda un juego en historico_juegos_equipos"""
        try:
            db.upsert(
                "historico_juegos_equipos",
                registro,
                on_conflict="fecha_juego,equipo",
            )
            return True
        except Exception as e:
            logger.error(f"Error guardando histórico: {e}")
            return False

    # ========================= CARGA INICIAL (UNA SOLA VEZ) =========================

    def cargar_inicial(self, dias: int = DIAS_HISTORICO) -> Dict:
        """
        Llamado UNA SOLA VEZ para poblar la BD con los últimos N días de juegos.
        Tarda ~30-40 min porque procesa 30 equipos × ~20 juegos = 600 boxscores.
        Después de esto, solo hay que llamar actualizar_ayer() cada mañana.
        """
        logger.info(f"🏗️  === CARGA INICIAL DE HISTÓRICO ({dias} días) ===")
        logger.info(f"⏳ Esto tomará 30-40 minutos. Solo se hace UNA VEZ.")

        end = get_today_et() - timedelta(days=1)  # ayer (hoy aún no terminó)
        start = end - timedelta(days=dias - 1)

        total_guardados = 0
        total_omitidos = 0
        total_errores = 0

        for team_abbr in config.EQUIPOS_MLB.keys():
            logger.info(f"📥 Cargando histórico de {team_abbr}...")
            juegos = self._obtener_juegos_equipo_rango(team_abbr, start, end)

            for juego in juegos:
                fecha_juego = juego.get("game_date")
                if not fecha_juego:
                    continue

                # Si ya está, no recargar
                if self._ya_existe_en_bd(team_abbr, fecha_juego):
                    total_omitidos += 1
                    continue

                registro = self._procesar_juego_equipo(team_abbr, juego)
                if registro and self._guardar_juego(registro):
                    total_guardados += 1
                else:
                    total_errores += 1

            logger.info(f"✅ {team_abbr} listo")

        resumen = {
            "guardados": total_guardados,
            "ya_existian": total_omitidos,
            "errores": total_errores,
            "rango": f"{start} a {end}",
        }
        logger.info(f"🎉 Carga inicial completa: {resumen}")
        return resumen

    # ========================= ACTUALIZACIÓN DIARIA =========================

    def actualizar_ayer(self) -> Dict:
        """
        Llamado CADA MAÑANA. Solo procesa juegos de AYER.
        Tarda ~5 min porque solo hay 1 día × 30 equipos = ~15-30 juegos.
        """
        ayer = get_yesterday_et()
        logger.info(f"🔄 === ACTUALIZANDO HISTÓRICO DE AYER ({ayer}) ===")

        total_nuevos = 0
        total_existentes = 0

        for team_abbr in config.EQUIPOS_MLB.keys():
            juegos = self._obtener_juegos_equipo_rango(team_abbr, ayer, ayer)

            for juego in juegos:
                fecha_juego = juego.get("game_date")
                if not fecha_juego:
                    continue

                if self._ya_existe_en_bd(team_abbr, fecha_juego):
                    total_existentes += 1
                    continue

                registro = self._procesar_juego_equipo(team_abbr, juego)
                if registro and self._guardar_juego(registro):
                    total_nuevos += 1
                    logger.info(
                        f"✅ Guardado: {team_abbr} {fecha_juego} ({registro['r']} carreras)"
                    )

        # Limpiar registros viejos (> DIAS_HISTORICO + buffer)
        self._limpiar_registros_viejos()

        resumen = {
            "nuevos": total_nuevos,
            "ya_existian": total_existentes,
            "fecha_procesada": ayer.isoformat(),
        }
        logger.info(f"✅ Actualización completa: {resumen}")
        return resumen

    def _limpiar_registros_viejos(self):
        """Elimina registros con más de (DIAS_HISTORICO + 10) días para que la BD no crezca"""
        try:
            limite = (get_today_et() - timedelta(days=DIAS_HISTORICO + 10)).isoformat()
            client = db.get_client()
            client.table("historico_juegos_equipos").delete().lt(
                "fecha_juego", limite
            ).execute()
            logger.debug(f"🧹 Registros anteriores a {limite} eliminados")
        except Exception as e:
            logger.warning(f"No se pudo limpiar registros viejos: {e}")

    # ========================= LECTURA DESDE BD =========================

    def get_juegos_equipo(self, team_abbr: str, num_games: int = 10) -> List[Dict]:
        """
        Lee desde BD los últimos N juegos de un equipo.
        Esta función es ULTRA RÁPIDA porque no llama a la API.
        """
        try:
            client = db.get_client()
            response = (
                client.table("historico_juegos_equipos")
                .select("*")
                .eq("equipo", team_abbr)
                .order("fecha_juego", desc=True)
                .limit(num_games)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Error leyendo histórico de {team_abbr}: {e}")
            return []

    def get_estado_cache(self) -> Dict:
        """Devuelve info sobre el estado del caché (cuántos días tiene cada equipo)"""
        try:
            estado = {}
            for team in config.EQUIPOS_MLB.keys():
                juegos = self.get_juegos_equipo(team, num_games=30)
                if juegos:
                    estado[team] = {
                        "total_juegos": len(juegos),
                        "ultimo_juego": juegos[0].get("fecha_juego"),
                        "primer_juego": juegos[-1].get("fecha_juego"),
                    }
                else:
                    estado[team] = {"total_juegos": 0, "ultimo_juego": None, "primer_juego": None}
            return estado
        except Exception as e:
            logger.error(f"Error obteniendo estado caché: {e}")
            return {}


def cargar_inicial_run(dias: int = DIAS_HISTORICO):
    """Helper para llamar carga inicial desde CLI o desde el bot"""
    collector = HistoricoCollector()
    return collector.cargar_inicial(dias)


def actualizar_ayer_run():
    """Helper para llamar actualización diaria"""
    collector = HistoricoCollector()
    return collector.actualizar_ayer()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "inicial":
        cargar_inicial_run()
    else:
        actualizar_ayer_run()
