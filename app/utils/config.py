"""
PicksProMLB - Configuración central del sistema
Carga variables de entorno y constantes globales
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# Cargar variables de entorno
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)


class Config:
    """Configuración global del sistema"""
    
    # ===== SUPABASE =====
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # service_role/secret key
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")  # publishable
    
    # ===== APIs EXTERNAS =====
    ODDS_API_KEY = os.getenv("ODDS_API_KEY")
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
    
    # ===== TELEGRAM =====
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    # ===== GENERAL =====
    TIMEZONE = os.getenv("TIMEZONE", "America/New_York")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # ===== HORAS DE TRIGGERS =====
    HOURS_BEFORE_FIRST_GAME = int(os.getenv("HOURS_BEFORE_FIRST_GAME", "4"))
    HOURS_BEFORE_UPDATE = int(os.getenv("HOURS_BEFORE_UPDATE", "1"))
    HOURS_AFTER_LAST_GAME = int(os.getenv("HOURS_AFTER_LAST_GAME", "2"))
    
    # ===== CONSTANTES MLB =====
    
    # Equipos MLB con sus abreviaciones oficiales
    EQUIPOS_MLB = {
        "ARI": "Arizona Diamondbacks",
        "ATL": "Atlanta Braves",
        "BAL": "Baltimore Orioles",
        "BOS": "Boston Red Sox",
        "CHC": "Chicago Cubs",
        "CHW": "Chicago White Sox",
        "CIN": "Cincinnati Reds",
        "CLE": "Cleveland Guardians",
        "COL": "Colorado Rockies",
        "DET": "Detroit Tigers",
        "HOU": "Houston Astros",
        "KCR": "Kansas City Royals",
        "LAA": "Los Angeles Angels",
        "LAD": "Los Angeles Dodgers",
        "MIA": "Miami Marlins",
        "MIL": "Milwaukee Brewers",
        "MIN": "Minnesota Twins",
        "NYM": "New York Mets",
        "NYY": "New York Yankees",
        "ATH": "Athletics",
        "PHI": "Philadelphia Phillies",
        "PIT": "Pittsburgh Pirates",
        "SDP": "San Diego Padres",
        "SEA": "Seattle Mariners",
        "SFG": "San Francisco Giants",
        "STL": "St. Louis Cardinals",
        "TBR": "Tampa Bay Rays",
        "TEX": "Texas Rangers",
        "TOR": "Toronto Blue Jays",
        "WSN": "Washington Nationals",
    }
    
    # Estadios y características especiales
    ESTADIOS_ESPECIALES = {
        "Coors Field": {
            "equipo": "COL",
            "altitud_pies": 5200,
            "factor_inflacion": 1.30,  # Los números aquí están inflados
            "alerta": "Números ofensivos inflados por altitud"
        },
        "Oracle Park": {
            "equipo": "SFG",
            "humedad_alta": True,
            "factor_supresion": 0.85,  # Suprime jonrones
            "alerta": "Estadio suprime poder por humedad y dimensiones"
        },
    }
    
    # ===== DEFINICIÓN DE LOS 10 FILTROS =====
    FILTROS = {
        "F1": {
            "descripcion": "wOBA diff >=0.040 + wRC+ diff >=30",
            "condicion": lambda eq, riv: (
                (eq["woba_l5"] - riv["woba_l5"]) >= 0.040 and
                (eq["wrc_plus_l5"] - riv["wrc_plus_l5"]) >= 30
            ),
            "efectividad_base": 79.07
        },
        "F2": {
            "descripcion": "OPS diff >=0.150 + wRC+ diff >=30",
            "condicion": lambda eq, riv: (
                (eq["ops_l5"] - riv["ops_l5"]) >= 0.150 and
                (eq["wrc_plus_l5"] - riv["wrc_plus_l5"]) >= 30
            ),
            "efectividad_base": 81.25
        },
        "F3": {
            "descripcion": "wRC+ diff >=30 + wRAA diff >9",
            "condicion": lambda eq, riv: (
                (eq["wrc_plus_l5"] - riv["wrc_plus_l5"]) >= 30 and
                (eq["wraa_l5"] - riv["wraa_l5"]) > 9
            ),
            "efectividad_base": 80.00
        },
        "F4": {
            "descripcion": "wOBA diff >=0.040 + OPS diff >=0.150",
            "condicion": lambda eq, riv: (
                (eq["woba_l5"] - riv["woba_l5"]) >= 0.040 and
                (eq["ops_l5"] - riv["ops_l5"]) >= 0.150
            ),
            "efectividad_base": 81.59
        },
        "F5": {
            "descripcion": "wRC+ >=50 + wRAA >12 + wOBA >=0.070",
            "condicion": lambda eq, riv: (
                (eq["wrc_plus_l5"] - riv["wrc_plus_l5"]) >= 50 and
                (eq["wraa_l5"] - riv["wraa_l5"]) > 12 and
                (eq["woba_l5"] - riv["woba_l5"]) >= 0.070
            ),
            "efectividad_base": 94.44,
            "es_filtro_estrella": True
        },
        "F6": {
            "descripcion": "wRC+ >=30 + wRAA >9 + wOBA >=0.040",
            "condicion": lambda eq, riv: (
                (eq["wrc_plus_l5"] - riv["wrc_plus_l5"]) >= 30 and
                (eq["wraa_l5"] - riv["wraa_l5"]) > 9 and
                (eq["woba_l5"] - riv["woba_l5"]) >= 0.040
            ),
            "efectividad_base": 83.33
        },
        "F7": {
            "descripcion": "wRC+ >=30 + wRAA >9 + OPS >=0.150",
            "condicion": lambda eq, riv: (
                (eq["wrc_plus_l5"] - riv["wrc_plus_l5"]) >= 30 and
                (eq["wraa_l5"] - riv["wraa_l5"]) > 9 and
                (eq["ops_l5"] - riv["ops_l5"]) >= 0.150
            ),
            "efectividad_base": 83.33
        },
        "F8": {
            "descripcion": "wRC+ >=30 + wOBA >=0.040 + OPS >=0.150",
            "condicion": lambda eq, riv: (
                (eq["wrc_plus_l5"] - riv["wrc_plus_l5"]) >= 30 and
                (eq["woba_l5"] - riv["woba_l5"]) >= 0.040 and
                (eq["ops_l5"] - riv["ops_l5"]) >= 0.150
            ),
            "efectividad_base": 82.05
        },
        "F9": {
            "descripcion": "wRC+ >=30 + wRAA >9 + BB/K >=0.2",
            "condicion": lambda eq, riv: (
                (eq["wrc_plus_l5"] - riv["wrc_plus_l5"]) >= 30 and
                (eq["wraa_l5"] - riv["wraa_l5"]) > 9 and
                (eq["bbk_l5"] - riv["bbk_l5"]) >= 0.2
            ),
            "efectividad_base": 90.00,
            "es_filtro_estrella": True
        },
        "F10": {
            "descripcion": "wRC+ >=40 + wRAA >9 + wOBA >=0.060",
            "condicion": lambda eq, riv: (
                (eq["wrc_plus_l5"] - riv["wrc_plus_l5"]) >= 40 and
                (eq["wraa_l5"] - riv["wraa_l5"]) > 9 and
                (eq["woba_l5"] - riv["woba_l5"]) >= 0.060
            ),
            "efectividad_base": 82.10
        },
    }
    
    # ===== ZONAS DE REBOTE TÉCNICO =====
    ZONAS_REBOTE = {
        "avg_l5_bajo": {"max": 0.150, "porcentaje": 77, "tipo": "rebote"},
        "avg_l5_alto": {"min": 0.350, "porcentaje": 100, "tipo": "caliente"},
        "obp_l5_alto": {"min": 0.400, "porcentaje": 82, "tipo": "caliente"},
        "slg_l5_bajo": {"max": 0.300, "porcentaje": 70, "tipo": "rebote"},
        "slg_l5_alto": {"min": 0.600, "porcentaje": 100, "tipo": "caliente"},
        "iso_l5_alto": {"min": 0.250, "porcentaje": 73, "tipo": "caliente"},
        "babip_l5_alto": {"min": 0.400, "porcentaje": 87.5, "tipo": "caliente"},
        "woba_l5_alto": {"min": 0.400, "porcentaje": 78, "tipo": "caliente"},
        "wrc_plus_l5_bajo": {"max": 50, "porcentaje": 77, "tipo": "rebote"},
        "wrc_plus_l5_alto": {"min": 140, "porcentaje": 71, "tipo": "caliente"},
    }
    
    # ===== UMBRALES DE DECISIÓN =====
    UMBRAL_DIRECTA = 8       # 8+ filtros = directa del día
    UMBRAL_COMBINACION = 6   # 6-7 filtros = combinación principal
    UMBRAL_COLCHON = 4       # 4-5 filtros = solo run line/colchón
    
    @classmethod
    def validar(cls):
        """Valida que todas las variables críticas estén configuradas"""
        criticas = {
            "SUPABASE_URL": cls.SUPABASE_URL,
            "SUPABASE_KEY": cls.SUPABASE_KEY,
            "ODDS_API_KEY": cls.ODDS_API_KEY,
            "OPENWEATHER_API_KEY": cls.OPENWEATHER_API_KEY,
            "GEMINI_API_KEY": cls.GEMINI_API_KEY,
            "TELEGRAM_BOT_TOKEN": cls.TELEGRAM_BOT_TOKEN,
        }
        
        faltantes = [k for k, v in criticas.items() if not v]
        if faltantes:
            logger.error(f"❌ Variables faltantes en .env: {faltantes}")
            return False
        
        logger.info("✅ Configuración validada correctamente")
        return True


# Instancia global
config = Config()
