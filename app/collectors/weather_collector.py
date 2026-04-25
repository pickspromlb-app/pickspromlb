"""
PicksProMLB - Recolector de Clima
Obtiene clima de cada estadio desde OpenWeather
"""

import requests
from datetime import datetime
from typing import Dict, List
from loguru import logger
from app.utils.database import db
from app.utils.config import config


# Coordenadas geográficas de cada estadio MLB
ESTADIOS_COORDS = {
    "Angel Stadium": {"lat": 33.8003, "lon": -117.8827, "team": "LAA"},
    "American Family Field": {"lat": 43.0280, "lon": -87.9712, "team": "MIL"},
    "Busch Stadium": {"lat": 38.6226, "lon": -90.1928, "team": "STL"},
    "Camden Yards": {"lat": 39.2839, "lon": -76.6217, "team": "BAL"},
    "Oriole Park at Camden Yards": {"lat": 39.2839, "lon": -76.6217, "team": "BAL"},
    "Chase Field": {"lat": 33.4453, "lon": -112.0667, "team": "ARI"},
    "Citi Field": {"lat": 40.7571, "lon": -73.8458, "team": "NYM"},
    "Citizens Bank Park": {"lat": 39.9061, "lon": -75.1665, "team": "PHI"},
    "Comerica Park": {"lat": 42.3390, "lon": -83.0485, "team": "DET"},
    "Coors Field": {"lat": 39.7559, "lon": -104.9942, "team": "COL"},
    "Daikin Park": {"lat": 29.7573, "lon": -95.3555, "team": "HOU"},
    "Minute Maid Park": {"lat": 29.7573, "lon": -95.3555, "team": "HOU"},
    "Dodger Stadium": {"lat": 34.0739, "lon": -118.2400, "team": "LAD"},
    "UNIQLO Field at Dodger Stadium": {"lat": 34.0739, "lon": -118.2400, "team": "LAD"},
    "Fenway Park": {"lat": 42.3467, "lon": -71.0972, "team": "BOS"},
    "Globe Life Field": {"lat": 32.7473, "lon": -97.0826, "team": "TEX"},
    "Great American Ball Park": {"lat": 39.0975, "lon": -84.5061, "team": "CIN"},
    "Kauffman Stadium": {"lat": 39.0517, "lon": -94.4803, "team": "KCR"},
    "loanDepot park": {"lat": 25.7781, "lon": -80.2197, "team": "MIA"},
    "Nationals Park": {"lat": 38.8729, "lon": -77.0074, "team": "WSN"},
    "Oakland Coliseum": {"lat": 37.7516, "lon": -122.2005, "team": "ATH"},
    "Sutter Health Park": {"lat": 38.5803, "lon": -121.5135, "team": "ATH"},
    "Oracle Park": {"lat": 37.7786, "lon": -122.3893, "team": "SFG"},
    "Petco Park": {"lat": 32.7073, "lon": -117.1566, "team": "SDP"},
    "PNC Park": {"lat": 40.4469, "lon": -80.0057, "team": "PIT"},
    "Progressive Field": {"lat": 41.4962, "lon": -81.6852, "team": "CLE"},
    "Rate Field": {"lat": 41.8299, "lon": -87.6338, "team": "CHW"},
    "Guaranteed Rate Field": {"lat": 41.8299, "lon": -87.6338, "team": "CHW"},
    "Rogers Centre": {"lat": 43.6414, "lon": -79.3894, "team": "TOR"},
    "T-Mobile Park": {"lat": 47.5914, "lon": -122.3325, "team": "SEA"},
    "Target Field": {"lat": 44.9817, "lon": -93.2776, "team": "MIN"},
    "Tropicana Field": {"lat": 27.7682, "lon": -82.6534, "team": "TBR"},
    "Truist Park": {"lat": 33.8908, "lon": -84.4678, "team": "ATL"},
    "Wrigley Field": {"lat": 41.9484, "lon": -87.6553, "team": "CHC"},
    "Yankee Stadium": {"lat": 40.8296, "lon": -73.9262, "team": "NYY"},
}


class WeatherCollector:
    """Recolecta clima de cada estadio MLB"""
    
    BASE_URL = "https://api.openweathermap.org/data/2.5"
    
    def __init__(self):
        self.api_key = config.OPENWEATHER_API_KEY
        if not self.api_key:
            logger.warning("⚠️ OPENWEATHER_API_KEY no configurada")
    
    def get_weather_for_stadium(self, stadium_name: str) -> Dict:
        """Obtiene clima actual para un estadio específico"""
        if not self.api_key:
            return {}
        
        coords = ESTADIOS_COORDS.get(stadium_name)
        if not coords:
            logger.warning(f"⚠️ Coordenadas no encontradas para: {stadium_name}")
            return {}
        
        url = f"{self.BASE_URL}/weather"
        params = {
            "lat": coords["lat"],
            "lon": coords["lon"],
            "appid": self.api_key,
            "units": "imperial",  # Fahrenheit y mph
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return self._parse_weather(data, stadium_name)
        except Exception as e:
            logger.error(f"❌ Error obteniendo clima para {stadium_name}: {e}")
            return {}
    
    def get_forecast_for_stadium(self, stadium_name: str, target_time: datetime) -> Dict:
        """
        Obtiene pronóstico del clima para una hora específica.
        Usa el endpoint de forecast (cada 3 horas).
        """
        if not self.api_key:
            return {}
        
        coords = ESTADIOS_COORDS.get(stadium_name)
        if not coords:
            return {}
        
        url = f"{self.BASE_URL}/forecast"
        params = {
            "lat": coords["lat"],
            "lon": coords["lon"],
            "appid": self.api_key,
            "units": "imperial",
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Buscar el forecast más cercano a la hora del juego
            forecasts = data.get("list", [])
            if not forecasts:
                return {}
            
            # Encontrar el forecast más cercano
            target_ts = target_time.timestamp()
            closest = min(forecasts, key=lambda f: abs(f["dt"] - target_ts))
            
            return self._parse_weather(closest, stadium_name)
        except Exception as e:
            logger.error(f"❌ Error obteniendo forecast para {stadium_name}: {e}")
            return {}
    
    def _parse_weather(self, data: Dict, stadium_name: str) -> Dict:
        """Parsea respuesta de OpenWeather al formato de DB"""
        try:
            main = data.get("main", {})
            wind = data.get("wind", {})
            
            temp_f = main.get("temp", 0)
            temp_c = round((temp_f - 32) * 5 / 9, 1)
            
            # Probabilidad de lluvia (en forecast viene como pop)
            rain_pct = int(data.get("pop", 0) * 100) if "pop" in data else 0
            
            # Dirección del viento en grados → texto
            wind_deg = wind.get("deg", 0)
            wind_dir = self._degrees_to_direction(wind_deg)
            
            return {
                "estadio": stadium_name,
                "clima_temp_f": round(temp_f, 1),
                "clima_temp_c": temp_c,
                "clima_humedad": main.get("humidity", 0),
                "clima_viento_mph": round(wind.get("speed", 0), 1),
                "clima_viento_direccion": wind_dir,
                "clima_lluvia_pct": rain_pct,
            }
        except Exception as e:
            logger.error(f"❌ Error parseando clima: {e}")
            return {}
    
    def _degrees_to_direction(self, degrees: float) -> str:
        """Convierte grados a dirección del viento (N, NE, E, SE, S, SW, W, NW)"""
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        idx = round(degrees / 45) % 8
        return directions[idx]
    
    def update_games_with_weather(self, games: List[Dict]) -> int:
        """Actualiza la tabla juegos con info de clima"""
        updated = 0
        for game in games:
            stadium = game.get("estadio")
            if not stadium:
                continue
            
            # Obtener forecast para la hora del juego
            game_time_str = game.get("hora_inicio")
            if game_time_str:
                try:
                    game_time = datetime.fromisoformat(game_time_str.replace("Z", "+00:00"))
                    weather = self.get_forecast_for_stadium(stadium, game_time)
                except:
                    weather = self.get_weather_for_stadium(stadium)
            else:
                weather = self.get_weather_for_stadium(stadium)
            
            if not weather:
                continue
            
            # Actualizar DB
            try:
                update_data = {k: v for k, v in weather.items() if k != "estadio"}
                db.update(
                    "juegos",
                    update_data,
                    {
                        "fecha": game["fecha"],
                        "equipo_local": game["equipo_local"],
                        "equipo_visitante": game["equipo_visitante"],
                    }
                )
                updated += 1
            except Exception as e:
                logger.error(f"❌ Error actualizando clima: {e}")
        
        logger.info(f"🌤️ {updated} juegos actualizados con clima")
        return updated


def run(games: List[Dict] = None):
    """Ejecuta el recolector de clima"""
    collector = WeatherCollector()
    
    # Si no se pasan juegos, obtenerlos de la DB
    if games is None:
        from datetime import date
        games = db.select("juegos", filters={"fecha": date.today().isoformat()})
    
    collector.update_games_with_weather(games)


if __name__ == "__main__":
    run()
