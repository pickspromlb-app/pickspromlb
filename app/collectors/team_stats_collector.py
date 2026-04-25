"""
PicksProMLB - Recolector de Estadísticas de Equipos
Calcula stats por ventanas (L1, L3, L5, L7, L10) usando MLB Stats API y pybaseball
"""

import statsapi
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from loguru import logger
from app.utils.database import db
from app.utils.config import config


# IDs de MLB para cada equipo (necesarios para statsapi)
MLB_TEAM_IDS = {
    "ARI": 109, "ATL": 144, "BAL": 110, "BOS": 111, "CHC": 112,
    "CHW": 145, "CIN": 113, "CLE": 114, "COL": 115, "DET": 116,
    "HOU": 117, "KCR": 118, "LAA": 108, "LAD": 119, "MIA": 146,
    "MIL": 158, "MIN": 142, "NYM": 121, "NYY": 147, "ATH": 133,
    "PHI": 143, "PIT": 134, "SDP": 135, "SEA": 136, "SFG": 137,
    "STL": 138, "TBR": 139, "TEX": 140, "TOR": 141, "WSN": 120,
}


class TeamStatsCollector:
    """Recolecta estadísticas de equipos por ventanas de juegos"""
    
    def __init__(self):
        self.windows = [1, 3, 5, 7, 10]  # Ventanas de últimos N juegos
    
    def get_team_recent_games(self, team_abbr: str, num_games: int = 10) -> List[Dict]:
        """
        Obtiene los últimos N juegos completados de un equipo.
        Usa MLB Stats API.
        """
        team_id = MLB_TEAM_IDS.get(team_abbr)
        if not team_id:
            logger.warning(f"⚠️ ID no encontrado para {team_abbr}")
            return []
        
        # Buscar juegos en los últimos 30 días
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        try:
            schedule = statsapi.schedule(
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                team=team_id
            )
        except Exception as e:
            logger.error(f"❌ Error obteniendo juegos de {team_abbr}: {e}")
            return []
        
        # Filtrar solo finalizados
        completed = [g for g in schedule if g.get("status") in ["Final", "Game Over"]]
        
        # Ordenar por fecha descendente y tomar los últimos N
        completed.sort(key=lambda x: x.get("game_date", ""), reverse=True)
        return completed[:num_games]
    
    def calculate_window_stats(self, team_abbr: str, games: List[Dict]) -> Dict:
        """
        Calcula estadísticas básicas de una ventana de juegos.
        Para stats avanzadas (wOBA, wRC+) usaremos pybaseball en otro método.
        """
        if not games:
            return {}
        
        team_id = MLB_TEAM_IDS.get(team_abbr)
        
        # Acumular stats
        total_runs = 0
        total_runs_against = 0
        wins = 0
        
        for game in games:
            if game.get("home_id") == team_id:
                total_runs += game.get("home_score", 0)
                total_runs_against += game.get("away_score", 0)
                if game.get("home_score", 0) > game.get("away_score", 0):
                    wins += 1
            else:
                total_runs += game.get("away_score", 0)
                total_runs_against += game.get("home_score", 0)
                if game.get("away_score", 0) > game.get("home_score", 0):
                    wins += 1
        
        return {
            "juegos": len(games),
            "carreras_hechas": total_runs,
            "carreras_recibidas": total_runs_against,
            "victorias": wins,
            "promedio_carreras": round(total_runs / len(games), 2) if games else 0,
        }
    
    def collect_advanced_stats(self, team_abbr: str, target_date: date = None) -> Dict:
        """
        Recolecta stats avanzadas usando pybaseball (FanGraphs).
        
        IMPORTANTE: Esta es una implementación base. Para producción,
        usaremos pybaseball.team_batting_bref() o consultaremos FanGraphs
        directamente con las ventanas de tiempo.
        """
        if target_date is None:
            target_date = date.today()
        
        try:
            from pybaseball import team_batting_bref
            
            # Obtener stats de la temporada
            year = target_date.year
            
            # NOTA: pybaseball no tiene endpoint directo para "últimos N juegos"
            # Necesitaremos calcularlo manualmente o usar otro método
            
            # Por ahora retornamos placeholder
            stats = {
                "team": team_abbr,
                "fecha": target_date.isoformat(),
                "fuente": "pybaseball",
                "nota": "Implementación pendiente con pybaseball + cálculo manual"
            }
            
            return stats
            
        except ImportError:
            logger.warning("⚠️ pybaseball no disponible, usando solo MLB Stats API")
            return {}
        except Exception as e:
            logger.error(f"❌ Error obteniendo stats avanzadas: {e}")
            return {}
    
    def collect_for_team(self, team_abbr: str, target_date: date = None) -> Dict:
        """
        Recolecta TODAS las stats de un equipo (todas las ventanas + avanzadas).
        """
        if target_date is None:
            target_date = date.today()
        
        logger.info(f"📊 Recolectando stats de {team_abbr}")
        
        # Obtener últimos 10 juegos
        recent_games = self.get_team_recent_games(team_abbr, num_games=10)
        
        if not recent_games:
            logger.warning(f"⚠️ No hay juegos recientes para {team_abbr}")
            return {}
        
        # Calcular stats por cada ventana
        result = {
            "fecha": target_date.isoformat(),
            "equipo": team_abbr,
        }
        
        for window in self.windows:
            window_games = recent_games[:window]
            stats = self.calculate_window_stats(team_abbr, window_games)
            
            # Mapear a campos de DB
            result[f"juegos_l{window}"] = stats.get("juegos", 0)
            result[f"carreras_l{window}"] = stats.get("carreras_hechas", 0)
        
        # Stats avanzadas (placeholder por ahora)
        advanced = self.collect_advanced_stats(team_abbr, target_date)
        result.update(advanced)
        
        return result
    
    def collect_for_all_teams(self, target_date: date = None) -> List[Dict]:
        """Recolecta stats de TODOS los equipos MLB"""
        if target_date is None:
            target_date = date.today()
        
        all_stats = []
        for team_abbr in config.EQUIPOS_MLB.keys():
            try:
                stats = self.collect_for_team(team_abbr, target_date)
                if stats:
                    all_stats.append(stats)
            except Exception as e:
                logger.error(f"❌ Error con {team_abbr}: {e}")
                continue
        
        logger.info(f"✅ Stats recolectadas para {len(all_stats)} equipos")
        return all_stats
    
    def save_to_db(self, team_stats: List[Dict]) -> int:
        """Guarda las stats en la tabla equipos_diario"""
        saved = 0
        for stats in team_stats:
            try:
                db.upsert("equipos_diario", stats, on_conflict="fecha,equipo")
                saved += 1
            except Exception as e:
                logger.error(f"❌ Error guardando stats de {stats.get('equipo')}: {e}")
        
        logger.info(f"💾 {saved}/{len(team_stats)} stats guardadas")
        return saved


def run():
    """Ejecuta el recolector de stats de equipos"""
    collector = TeamStatsCollector()
    stats = collector.collect_for_all_teams()
    collector.save_to_db(stats)
    return stats


if __name__ == "__main__":
    run()
