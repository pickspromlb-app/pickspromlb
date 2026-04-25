"""
PicksProMLB - Recolector de Calendario MLB
Obtiene los juegos programados del día desde MLB Stats API
"""

import statsapi
from datetime import datetime, date
from typing import List, Dict
from loguru import logger
from app.utils.database import db
from app.utils.config import config


# Mapeo de IDs de MLB Stats API a nuestras abreviaciones
TEAM_ID_MAP = {
    109: "ARI", 144: "ATL", 110: "BAL", 111: "BOS", 112: "CHC",
    145: "CHW", 113: "CIN", 114: "CLE", 115: "COL", 116: "DET",
    117: "HOU", 118: "KCR", 108: "LAA", 119: "LAD", 146: "MIA",
    158: "MIL", 142: "MIN", 121: "NYM", 147: "NYY", 133: "ATH",
    143: "PHI", 134: "PIT", 135: "SDP", 136: "SEA", 137: "SFG",
    138: "STL", 139: "TBR", 140: "TEX", 141: "TOR", 120: "WSN",
}


class CalendarCollector:
    """Recolecta el calendario de juegos MLB del día"""
    
    def __init__(self):
        self.team_map = TEAM_ID_MAP
    
    def get_games_for_date(self, target_date: date = None) -> List[Dict]:
        """
        Obtiene todos los juegos programados para una fecha específica.
        Si no se pasa fecha, usa la de hoy.
        """
        if target_date is None:
            target_date = date.today()
        
        date_str = target_date.strftime("%Y-%m-%d")
        logger.info(f"📅 Obteniendo juegos para {date_str}")
        
        try:
            schedule = statsapi.schedule(date=date_str)
        except Exception as e:
            logger.error(f"❌ Error obteniendo schedule: {e}")
            return []
        
        if not schedule:
            logger.warning(f"⚠️ No hay juegos para {date_str}")
            return []
        
        games = []
        for game in schedule:
            try:
                game_data = self._parse_game(game, target_date)
                if game_data:
                    games.append(game_data)
            except Exception as e:
                logger.warning(f"⚠️ Error parseando juego: {e}")
                continue
        
        logger.info(f"✅ {len(games)} juegos encontrados para {date_str}")
        return games
    
    def _parse_game(self, game: dict, target_date: date) -> Dict:
        """Parsea un juego del schedule a nuestro formato"""
        
        # Obtener abreviaciones (algunos campos vienen del API)
        home_team = game.get("home_name", "")
        away_team = game.get("away_name", "")
        
        # Mapear nombres a abreviaciones
        home_abbr = self._name_to_abbr(home_team)
        away_abbr = self._name_to_abbr(away_team)
        
        if not home_abbr or not away_abbr:
            logger.warning(f"⚠️ No se pudo mapear: {home_team} vs {away_team}")
            return None
        
        # Hora del juego
        game_datetime = game.get("game_datetime", "")
        
        return {
            "fecha": target_date.isoformat(),
            "game_id": str(game.get("game_id", "")),
            "equipo_local": home_abbr,
            "equipo_visitante": away_abbr,
            "estadio": game.get("venue_name", ""),
            "hora_inicio": game_datetime,
            "pitcher_local": game.get("home_probable_pitcher", ""),
            "pitcher_visitante": game.get("away_probable_pitcher", ""),
            "estado": self._map_status(game.get("status", "")),
            "resultado_local": game.get("home_score") if game.get("status") == "Final" else None,
            "resultado_visitante": game.get("away_score") if game.get("status") == "Final" else None,
        }
    
    def _name_to_abbr(self, team_name: str) -> str:
        """Convierte nombre completo a abreviación"""
        for abbr, full_name in config.EQUIPOS_MLB.items():
            if team_name.lower() in full_name.lower() or full_name.lower() in team_name.lower():
                return abbr
        return None
    
    def _map_status(self, status: str) -> str:
        """Mapea el estado del juego"""
        status_map = {
            "Scheduled": "programado",
            "Pre-Game": "programado",
            "Warmup": "programado",
            "In Progress": "en_curso",
            "Final": "finalizado",
            "Game Over": "finalizado",
            "Postponed": "suspendido",
            "Cancelled": "suspendido",
            "Suspended": "suspendido",
        }
        return status_map.get(status, "programado")
    
    def save_to_db(self, games: List[Dict]) -> int:
        """Guarda los juegos en Supabase"""
        if not games:
            return 0
        
        saved = 0
        for game in games:
            try:
                # Upsert: si existe, actualiza; si no, inserta
                db.upsert("juegos", game, on_conflict="fecha,equipo_local,equipo_visitante")
                saved += 1
            except Exception as e:
                logger.error(f"❌ Error guardando {game['equipo_local']} vs {game['equipo_visitante']}: {e}")
        
        logger.info(f"💾 {saved}/{len(games)} juegos guardados en DB")
        return saved
    
    def get_first_and_last_game_times(self, target_date: date = None) -> tuple:
        """
        Retorna (hora_primer_juego, hora_ultimo_juego) del día.
        Útil para programar los triggers dinámicos.
        """
        games = self.get_games_for_date(target_date)
        if not games:
            return None, None
        
        times = [
            datetime.fromisoformat(g["hora_inicio"].replace("Z", "+00:00"))
            for g in games if g.get("hora_inicio")
        ]
        
        if not times:
            return None, None
        
        return min(times), max(times)


def run():
    """Ejecuta el recolector de calendario"""
    collector = CalendarCollector()
    games = collector.get_games_for_date()
    collector.save_to_db(games)
    return games


if __name__ == "__main__":
    run()
