"""
PicksProMLB - Recolector de Odds (Cuotas)
Obtiene moneylines, run lines y totales desde The Odds API
"""

import requests
from datetime import date, datetime
from typing import List, Dict
from loguru import logger
from app.utils.database import db
from app.utils.config import config


# Mapeo de nombres de equipos en The Odds API a nuestras abreviaciones
ODDS_API_TEAM_MAP = {
    "Arizona Diamondbacks": "ARI",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CHW",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KCR",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Oakland Athletics": "ATH",
    "Athletics": "ATH",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SDP",
    "Seattle Mariners": "SEA",
    "San Francisco Giants": "SFG",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TBR",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSN",
}


class OddsCollector:
    """Recolecta odds (cuotas) de The Odds API"""
    
    BASE_URL = "https://api.the-odds-api.com/v4"
    SPORT = "baseball_mlb"
    REGIONS = "us"  # us, uk, eu, au
    MARKETS = "h2h,spreads,totals"  # moneyline, run line, total
    BOOKMAKERS = "draftkings,fanduel,betmgm,williamhill_us"
    
    def __init__(self):
        self.api_key = config.ODDS_API_KEY
        if not self.api_key:
            logger.warning("⚠️ ODDS_API_KEY no configurada")
    
    def fetch_odds(self) -> List[Dict]:
        """Obtiene odds actuales de todos los juegos MLB"""
        if not self.api_key:
            return []
        
        url = f"{self.BASE_URL}/sports/{self.SPORT}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": self.REGIONS,
            "markets": self.MARKETS,
            "oddsFormat": "american",  # +120, -150, etc.
            "dateFormat": "iso",
            "bookmakers": self.BOOKMAKERS,
        }
        
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            # Logs de uso de API
            requests_used = response.headers.get("x-requests-used", "?")
            requests_remaining = response.headers.get("x-requests-remaining", "?")
            logger.info(f"📡 Odds API: {requests_used} usadas, {requests_remaining} restantes")
            
            return response.json()
        except Exception as e:
            logger.error(f"❌ Error obteniendo odds: {e}")
            return []
    
    def parse_odds(self, raw_odds: List[Dict]) -> List[Dict]:
        """Parsea las odds al formato de nuestra DB"""
        parsed = []
        
        for game in raw_odds:
            try:
                home_team = ODDS_API_TEAM_MAP.get(game.get("home_team"))
                away_team = ODDS_API_TEAM_MAP.get(game.get("away_team"))
                
                if not home_team or not away_team:
                    continue
                
                game_time = game.get("commence_time")
                game_date = datetime.fromisoformat(game_time.replace("Z", "+00:00")).date()
                
                # Obtener mejores odds (promediadas o de un bookmaker específico)
                bookmakers = game.get("bookmakers", [])
                if not bookmakers:
                    continue
                
                # Usar el primer bookmaker disponible (DraftKings preferido)
                bookmaker = bookmakers[0]
                markets = {m["key"]: m for m in bookmaker.get("markets", [])}
                
                # Moneyline (h2h)
                ml_local = ml_visit = None
                if "h2h" in markets:
                    for outcome in markets["h2h"].get("outcomes", []):
                        team_abbr = ODDS_API_TEAM_MAP.get(outcome.get("name"))
                        if team_abbr == home_team:
                            ml_local = outcome.get("price")
                        elif team_abbr == away_team:
                            ml_visit = outcome.get("price")
                
                # Run Line (spreads)
                rl_local = rl_visit = None
                rl_local_odds = rl_visit_odds = None
                if "spreads" in markets:
                    for outcome in markets["spreads"].get("outcomes", []):
                        team_abbr = ODDS_API_TEAM_MAP.get(outcome.get("name"))
                        if team_abbr == home_team:
                            rl_local = outcome.get("point")
                            rl_local_odds = outcome.get("price")
                        elif team_abbr == away_team:
                            rl_visit = outcome.get("point")
                            rl_visit_odds = outcome.get("price")
                
                # Total
                total_runs = None
                if "totals" in markets:
                    outcomes = markets["totals"].get("outcomes", [])
                    if outcomes:
                        total_runs = outcomes[0].get("point")
                
                parsed.append({
                    "fecha": game_date.isoformat(),
                    "equipo_local": home_team,
                    "equipo_visitante": away_team,
                    "ml_local": ml_local,
                    "ml_visitante": ml_visit,
                    "rl_local": rl_local,
                    "rl_visitante": rl_visit,
                    "rl_local_odds": rl_local_odds,
                    "rl_visitante_odds": rl_visit_odds,
                    "total_runs": total_runs,
                    "odds_snapshot": {
                        "fetched_at": datetime.now().isoformat(),
                        "bookmaker": bookmaker.get("key"),
                        "raw": game,
                    },
                })
            except Exception as e:
                logger.warning(f"⚠️ Error parseando odds de juego: {e}")
                continue
        
        logger.info(f"✅ {len(parsed)} juegos con odds parseados")
        return parsed
    
    def update_db(self, odds_list: List[Dict]) -> int:
        """Actualiza las odds en la tabla juegos"""
        updated = 0
        for odds in odds_list:
            try:
                # Solo actualizar campos de odds (no insertar juego nuevo)
                update_data = {k: v for k, v in odds.items() 
                              if k not in ["fecha", "equipo_local", "equipo_visitante"]}
                
                db.update(
                    "juegos",
                    update_data,
                    {
                        "fecha": odds["fecha"],
                        "equipo_local": odds["equipo_local"],
                        "equipo_visitante": odds["equipo_visitante"]
                    }
                )
                updated += 1
            except Exception as e:
                logger.error(f"❌ Error actualizando odds: {e}")
        
        logger.info(f"💾 {updated}/{len(odds_list)} juegos con odds actualizados")
        return updated


def run():
    """Ejecuta el recolector de odds"""
    collector = OddsCollector()
    raw = collector.fetch_odds()
    parsed = collector.parse_odds(raw)
    collector.update_db(parsed)
    return parsed


if __name__ == "__main__":
    run()
