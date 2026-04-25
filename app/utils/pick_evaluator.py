"""
PicksProMLB - Evaluador de Picks
==========================================================
Evalúa CORRECTAMENTE el resultado de un pick según su tipo.

Tipos soportados:
  - ML (Moneyline): equipo gana
  - RL (Run Line): equipo gana o pierde por menos del handicap
    * RL +1.5, RL +2.5, RL +3.5 (favorables)
    * RL -1.5, RL -2.5 (desfavorables)
  - F5 RL: Run Line en los primeros 5 innings
  - F5 ML: Moneyline en los primeros 5 innings
  - OVER/UNDER total: total de carreras del juego
  - TEAM TOTAL O/U: carreras de un solo equipo

NOTA: El campo 'tipo_pick' debe seguir convención:
  "ML", "RL+1.5", "RL+2.5", "RL+3.5", "RL-1.5",
  "F5_ML", "F5_RL+1.5",
  "OVER_8.5", "UNDER_9.5",
  "TEAM_OVER_4.5", "TEAM_UNDER_3.5"
"""

import re
from typing import Dict, Optional, Tuple
from loguru import logger


def parse_tipo_pick(tipo_str: str) -> Tuple[str, Optional[float]]:
    """
    Parsea el campo tipo_pick y devuelve (categoría, línea).

    Acepta múltiples formatos para máxima compatibilidad:
      "ML"             → ("ML", None)
      "Moneyline"      → ("ML", None)
      "RL+1.5"         → ("RL", 1.5)
      "RL +1.5"        → ("RL", 1.5)        ← con espacio
      "Run Line +1.5"  → ("RL", 1.5)        ← formato humano
      "RL-1.5"         → ("RL", -1.5)
      "F5_RL+1.5"      → ("F5_RL", 1.5)
      "OVER_8.5"       → ("OVER", 8.5)
      "Over 8.5"       → ("OVER", 8.5)      ← formato humano
      "TEAM_OVER_4.5"  → ("TEAM_OVER", 4.5)
      "Team Total Over 2.5" → ("TEAM_OVER", 2.5)  ← formato humano
    """
    if not tipo_str:
        return ("UNKNOWN", None)

    # Normalizar: mayúsculas, sin espacios, _ en vez de espacios y guiones múltiples
    raw = str(tipo_str).strip().upper()
    t = re.sub(r"\s+", "_", raw)  # espacios → _
    t = re.sub(r"_+", "_", t)     # múltiples _ → uno
    # Eliminar palabras descriptivas comunes para simplificar matching
    t_simple = (
        t.replace("MONEYLINE", "ML")
         .replace("RUN_LINE", "RL")
         .replace("RUNLINE", "RL")
         .replace("TEAM_TOTAL_OVER", "TEAM_OVER")
         .replace("TEAM_TOTAL_UNDER", "TEAM_UNDER")
         .replace("MAS_DE_", "OVER_")
         .replace("MENOS_DE_", "UNDER_")
    )

    # Moneyline simple
    if t_simple == "ML":
        return ("ML", None)

    # Moneyline en 5 innings
    if t_simple in ("F5_ML", "F5ML"):
        return ("F5_ML", None)

    # Run Line (con o sin signo) — soporta "RL+1.5", "RL_+1.5", "RL+_1.5"
    m = re.match(r"^RL[_]?([+-]?\d+\.?\d*)$", t_simple)
    if m:
        return ("RL", float(m.group(1)))

    # F5 Run Line
    m = re.match(r"^F5[_-]?RL[_]?([+-]?\d+\.?\d*)$", t_simple)
    if m:
        return ("F5_RL", float(m.group(1)))

    # Team Total Over
    m = re.match(r"^TEAM_OVER[_]?(\d+\.?\d*)$", t_simple)
    if m:
        return ("TEAM_OVER", float(m.group(1)))

    # Team Total Under
    m = re.match(r"^TEAM_UNDER[_]?(\d+\.?\d*)$", t_simple)
    if m:
        return ("TEAM_UNDER", float(m.group(1)))

    # Over total (debe ir DESPUÉS de TEAM_OVER para no matchear primero)
    m = re.match(r"^OVER[_]?(\d+\.?\d*)$", t_simple)
    if m:
        return ("OVER", float(m.group(1)))

    # Under total
    m = re.match(r"^UNDER[_]?(\d+\.?\d*)$", t_simple)
    if m:
        return ("UNDER", float(m.group(1)))

    logger.warning(f"⚠️ Tipo de pick no reconocido: '{tipo_str}'. Asumiendo ML.")
    return ("ML", None)


def _es_juego_finalizado(juego: Dict) -> bool:
    """Verifica que el juego esté finalizado y tenga resultados"""
    if juego.get("estado") != "finalizado":
        return False
    if juego.get("resultado_local") is None or juego.get("resultado_visitante") is None:
        return False
    return True


def _get_equipo_apostado(pick: Dict, juego: Dict) -> Tuple[str, str]:
    """
    Devuelve (equipo_apostado, equipo_rival) según el pick.
    Si no se puede determinar, devuelve (None, None).
    """
    equipo_apostado = pick.get("equipo") or pick.get("favorito") or pick.get("equipo_pick")
    if not equipo_apostado:
        return (None, None)

    local = juego.get("equipo_local")
    visit = juego.get("equipo_visitante")

    if equipo_apostado == local:
        return (local, visit)
    if equipo_apostado == visit:
        return (visit, local)

    return (None, None)


def evaluate_pick_result(pick: Dict, juego: Dict) -> Optional[bool]:
    """
    Evalúa si un pick GANÓ, PERDIÓ o no se puede evaluar.

    Devuelve:
      True  → pick ganador
      False → pick perdedor
      None  → no se puede evaluar (juego no finalizado, push, datos faltantes, etc.)

    Args:
        pick: dict con al menos { 'tipo_pick': str, 'equipo' o 'favorito': str }
        juego: dict con resultados { 'resultado_local': int, 'resultado_visitante': int,
                                     'equipo_local': str, 'equipo_visitante': str, 'estado': str }
    """
    if not _es_juego_finalizado(juego):
        return None

    tipo_str = pick.get("tipo_pick", "")
    categoria, linea = parse_tipo_pick(tipo_str)

    rl = juego.get("resultado_local") or 0
    rv = juego.get("resultado_visitante") or 0
    total = rl + rv

    # Para picks que requieren equipo
    equipo_apostado, _ = _get_equipo_apostado(pick, juego)

    # ========================= MONEYLINE =========================
    if categoria == "ML":
        if not equipo_apostado:
            logger.warning(f"ML sin equipo identificable: {pick}")
            return None
        if equipo_apostado == juego.get("equipo_local"):
            return rl > rv
        else:
            return rv > rl

    # ========================= RUN LINE =========================
    if categoria == "RL":
        if not equipo_apostado or linea is None:
            logger.warning(f"RL sin equipo o línea: {pick}")
            return None
        # carreras del equipo apostado vs rival
        if equipo_apostado == juego.get("equipo_local"):
            diff = rl - rv  # local
        else:
            diff = rv - rl  # visitante
        # diff + linea > 0 → gana el pick
        # Ej: equipo pierde 5-3, línea +1.5 → diff = -2 + 1.5 = -0.5 → pierde
        # Ej: equipo pierde 4-3, línea +1.5 → diff = -1 + 1.5 = 0.5 → gana
        ajustado = diff + linea
        if ajustado > 0:
            return True
        if ajustado < 0:
            return False
        # ajustado == 0 → push (en líneas .0 puras), tratar como None
        return None

    # ========================= OVER / UNDER total =========================
    if categoria == "OVER":
        if linea is None:
            return None
        if total > linea:
            return True
        if total < linea:
            return False
        return None  # push

    if categoria == "UNDER":
        if linea is None:
            return None
        if total < linea:
            return True
        if total > linea:
            return False
        return None

    # ========================= TEAM TOTAL =========================
    if categoria == "TEAM_OVER":
        if not equipo_apostado or linea is None:
            return None
        carreras_equipo = rl if equipo_apostado == juego.get("equipo_local") else rv
        if carreras_equipo > linea:
            return True
        if carreras_equipo < linea:
            return False
        return None

    if categoria == "TEAM_UNDER":
        if not equipo_apostado or linea is None:
            return None
        carreras_equipo = rl if equipo_apostado == juego.get("equipo_local") else rv
        if carreras_equipo < linea:
            return True
        if carreras_equipo > linea:
            return False
        return None

    # ========================= F5 (primeros 5 innings) =========================
    # NOTA: Requiere que el juego tenga resultados de los primeros 5 innings.
    # Si no están disponibles, devolvemos None.
    if categoria in ("F5_ML", "F5_RL"):
        rl_f5 = juego.get("f5_resultado_local")
        rv_f5 = juego.get("f5_resultado_visitante")

        if rl_f5 is None or rv_f5 is None:
            logger.debug(f"F5 sin datos disponibles para juego {juego.get('id')}")
            return None

        if categoria == "F5_ML":
            if not equipo_apostado:
                return None
            if equipo_apostado == juego.get("equipo_local"):
                return rl_f5 > rv_f5
            return rv_f5 > rl_f5

        # F5_RL
        if categoria == "F5_RL":
            if not equipo_apostado or linea is None:
                return None
            if equipo_apostado == juego.get("equipo_local"):
                diff = rl_f5 - rv_f5
            else:
                diff = rv_f5 - rl_f5
            ajustado = diff + linea
            if ajustado > 0:
                return True
            if ajustado < 0:
                return False
            return None

    logger.warning(f"Tipo de pick no manejado: '{tipo_str}' (categoría: {categoria})")
    return None


def evaluate_combinado(picks_list: list, juegos_dict: Dict[str, Dict]) -> Optional[bool]:
    """
    Evalúa un parlay/combinado: gana solo si TODOS los picks ganan.
    Si alguno no se puede evaluar (None), todo el combinado es None.

    Args:
        picks_list: lista de dicts pick, cada uno con su tipo_pick y equipo
        juegos_dict: dict { matchup_key: juego_dict }
    """
    if not picks_list:
        return None

    todos_ganados = True
    for pick in picks_list:
        # Identificar el juego del pick
        equipo = pick.get("equipo") or pick.get("favorito")
        juego = None
        for j in juegos_dict.values():
            if j.get("equipo_local") == equipo or j.get("equipo_visitante") == equipo:
                juego = j
                break

        if not juego:
            return None  # No podemos evaluar

        resultado = evaluate_pick_result(pick, juego)
        if resultado is None:
            return None  # Algún pick sin evaluar
        if resultado is False:
            return False  # Un perdedor mata el parlay
        # Si es True, sigue evaluando

    return True
