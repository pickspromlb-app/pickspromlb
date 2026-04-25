"""
PicksProMLB - Utilidades de tiempo y zona horaria
==========================================================
CRÍTICO: NO usar date.today() ni datetime.now() sin zona horaria.
A las 11 PM Orlando (ET) ya es "mañana" en UTC, lo que causa que el sistema
procese fechas equivocadas. SIEMPRE usar estas helpers.
"""

from datetime import date, datetime, timezone
import pytz
from app.utils.config import config


def _get_tz():
    """Devuelve el objeto timezone configurado (default: America/New_York)"""
    return pytz.timezone(config.TIMEZONE)


def get_now_et() -> datetime:
    """
    Devuelve datetime actual EN LA ZONA HORARIA del sistema (ET por defecto).
    Reemplazo de datetime.now() para evitar bugs de UTC.
    """
    return datetime.now(_get_tz())


def get_today_et() -> date:
    """
    Devuelve la fecha de HOY EN ZONA ET.
    Reemplazo de date.today() para evitar que a las 11 PM ET se procese mañana.

    Ejemplo del bug que arregla:
      - 11:30 PM en Orlando (ET) → date.today() devolvía mañana (UTC ya cambió)
      - get_today_et() → devuelve correctamente la fecha de hoy en ET
    """
    return get_now_et().date()


def get_yesterday_et() -> date:
    """Devuelve la fecha de AYER en zona ET"""
    from datetime import timedelta
    return get_today_et() - timedelta(days=1)


def to_et(dt: datetime) -> datetime:
    """Convierte cualquier datetime a la zona ET"""
    if dt.tzinfo is None:
        # Asumir UTC si viene sin tzinfo
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_get_tz())


def parse_iso_to_et(iso_string: str) -> datetime:
    """Parsea un ISO datetime y lo convierte a ET. Si no tiene TZ, asume UTC."""
    if not iso_string:
        return None
    try:
        # Manejar el sufijo Z (UTC)
        s = str(iso_string).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return to_et(dt)
    except Exception:
        return None
