"""
PicksProMLB - Generador de Listín Estilo Tipster
Construye el listín completo del día replicando el formato del tipster venezolano:
- Tabla "lo que va de temporada"
- Tabla "estadísticas avanzadas"
- Tabla "como llegan en últimos 10 días" (L10, L7, L5, L3, L1)
- Tabla bullpenes
- Tabla filtros aplicados
- Tabla horarios + jugadas recomendadas
- Picks: directa, combinaciones, alternativas
- Histórico de efectividad de filtros

Genera 2 archivos por día: listin_YYYY-MM-DD.json y listin_YYYY-MM-DD.html
"""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

from app.utils.database import db
from app.utils.config import config
from app.utils.time_utils import get_today_et


class ListinBuilder:
    """Genera el listín diario completo estilo tipster"""

    def __init__(self):
        self.output_dir = Path("/tmp/pickspromlb_listines")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ========================= CONSTRUCCIÓN DE DATOS =========================

    def build(self, target_date: date = None) -> Optional[Dict]:
        """Construye el listín completo del día"""
        if target_date is None:
            target_date = get_today_et()

        fecha_str = target_date.isoformat()

        # Obtener juegos del día
        juegos = db.select("juegos", filters={"fecha": fecha_str})
        if not juegos:
            logger.warning(f"⚠️ No hay juegos para {fecha_str}")
            return None

        # Ordenar por hora_inicio (ascendente)
        juegos.sort(key=lambda j: j.get("hora_inicio") or "")

        # Para cada juego, construir el bloque completo
        bloques_juegos = []
        for juego in juegos:
            bloque = self._construir_bloque_juego(juego, fecha_str)
            if bloque:
                bloques_juegos.append(bloque)

        # Construir tabla de filtros aplicados
        tabla_filtros = self._construir_tabla_filtros(bloques_juegos)

        # Construir picks recomendados
        picks = self._construir_picks(bloques_juegos)

        # Efectividad histórica de filtros
        efectividad_filtros = self._obtener_efectividad_filtros()

        # Construir listín completo
        listin = {
            "metadata": {
                "fecha": fecha_str,
                "fecha_display": target_date.strftime("%d/%m/%Y"),
                "generado_en": datetime.now().isoformat(),
                "total_juegos": len(juegos),
                "version": "2.0_tipster",
            },
            "juegos": bloques_juegos,
            "tabla_filtros": tabla_filtros,
            "picks": picks,
            "efectividad_filtros": efectividad_filtros,
        }

        return listin

    def _construir_bloque_juego(self, juego: Dict, fecha_str: str) -> Optional[Dict]:
        """Construye el bloque completo de UN juego con sus 4 tablas"""
        local = juego.get("equipo_local")
        visit = juego.get("equipo_visitante")
        if not local or not visit:
            return None

        # Stats de equipos
        stats_local = self._get_stats_equipo(fecha_str, local)
        stats_visit = self._get_stats_equipo(fecha_str, visit)

        # Bullpens
        bp_local = self._get_bullpen(fecha_str, local)
        bp_visit = self._get_bullpen(fecha_str, visit)

        # Análisis de filtros
        analisis = self._get_analisis_filtros(fecha_str, local, visit)

        # Hora formateada en ET
        hora_str = self._formatear_hora_et(juego.get("hora_inicio"))

        return {
            "matchup": f"{visit} @ {local}",
            "matchup_completo": f"{config.EQUIPOS_MLB.get(visit, visit)} @ {config.EQUIPOS_MLB.get(local, local)}",
            "equipo_local": local,
            "equipo_visitante": visit,
            "hora_et": hora_str,
            "estadio": juego.get("estadio", ""),
            "pitcher_local": juego.get("pitcher_local") or "TBD",
            "pitcher_visitante": juego.get("pitcher_visitante") or "TBD",
            "mercado": {
                "ml_local": juego.get("ml_local"),
                "ml_visitante": juego.get("ml_visitante"),
                "rl_local": juego.get("rl_local"),
                "rl_visitante": juego.get("rl_visitante"),
                "total": juego.get("total_runs"),
            },
            "clima": {
                "temp_c": juego.get("clima_temp_c"),
                "temp_f": juego.get("clima_temp_f"),
                "humedad": juego.get("clima_humedad"),
                "viento_mph": juego.get("clima_viento_mph"),
                "viento_dir": juego.get("clima_viento_direccion"),
                "lluvia_pct": juego.get("clima_lluvia_pct"),
            },
            "tabla_temporada": self._construir_tabla_temporada(
                local, stats_local, visit, stats_visit
            ),
            "tabla_avanzadas": self._construir_tabla_avanzadas(
                local, stats_local, visit, stats_visit
            ),
            "tabla_ultimos_dias": self._construir_tabla_ultimos_dias(
                local, stats_local, visit, stats_visit
            ),
            "tabla_bullpenes": self._construir_tabla_bullpenes(
                local, bp_local, visit, bp_visit
            ),
            "analisis": self._formatear_analisis(analisis) if analisis else None,
        }

    def _get_stats_equipo(self, fecha: str, equipo: str) -> Dict:
        result = db.select("equipos_diario", filters={"fecha": fecha, "equipo": equipo})
        return result[0] if result else {}

    def _get_bullpen(self, fecha: str, equipo: str) -> Dict:
        result = db.select("bullpenes_diario", filters={"fecha": fecha, "equipo": equipo})
        return result[0] if result else {}

    def _get_analisis_filtros(self, fecha: str, local: str, visit: str) -> Optional[Dict]:
        """Busca el análisis de filtros (puede estar en cualquier dirección)"""
        result = db.select(
            "filtros_aplicados",
            filters={"fecha": fecha, "equipo_favorecido": local, "equipo_rival": visit},
        )
        if not result:
            result = db.select(
                "filtros_aplicados",
                filters={"fecha": fecha, "equipo_favorecido": visit, "equipo_rival": local},
            )
        return result[0] if result else None

    def _formatear_hora_et(self, hora_iso: str) -> str:
        """Convierte ISO datetime a formato '7:10 PM ET'"""
        if not hora_iso:
            return "TBD"
        try:
            import pytz
            dt = datetime.fromisoformat(str(hora_iso).replace("Z", "+00:00"))
            et = pytz.timezone("America/New_York")
            dt_et = dt.astimezone(et)
            return dt_et.strftime("%I:%M %p ET").lstrip("0")
        except Exception:
            return str(hora_iso)

    # ========================= TABLAS POR JUEGO =========================

    def _construir_tabla_temporada(
        self, local: str, sl: Dict, visit: str, sv: Dict
    ) -> Dict:
        """Tabla A: lo que va de temporada (stats acumuladas)"""
        return {
            "titulo": "LO QUE VA DE TEMPORADA",
            "filas": [
                {
                    "equipo": local,
                    "juegos": sl.get("juegos_l10", 0),
                    "carreras": sl.get("carreras_l10", 0),
                    "avg": sl.get("avg_temp"),
                    "obp": sl.get("obp_temp"),
                    "slg": sl.get("slg_temp"),
                    "ops": sl.get("ops_temp"),
                },
                {
                    "equipo": visit,
                    "juegos": sv.get("juegos_l10", 0),
                    "carreras": sv.get("carreras_l10", 0),
                    "avg": sv.get("avg_temp"),
                    "obp": sv.get("obp_temp"),
                    "slg": sv.get("slg_temp"),
                    "ops": sv.get("ops_temp"),
                },
            ],
        }

    def _construir_tabla_avanzadas(
        self, local: str, sl: Dict, visit: str, sv: Dict
    ) -> Dict:
        """Tabla B: estadísticas avanzadas sabermétricas"""
        return {
            "titulo": "ESTADÍSTICAS AVANZADAS",
            "filas": [
                {
                    "equipo": local,
                    "bb_pct": self._fmt_pct(sl.get("bb_pct_temp")),
                    "k_pct": self._fmt_pct(sl.get("k_pct_temp")),
                    "bbk": sl.get("bbk_temp"),
                    "iso": sl.get("iso_temp"),
                    "babip": sl.get("babip_temp"),
                    "wraa": sl.get("wraa_temp"),
                    "woba": sl.get("woba_temp"),
                    "wrc_plus": sl.get("wrc_plus_temp"),
                },
                {
                    "equipo": visit,
                    "bb_pct": self._fmt_pct(sv.get("bb_pct_temp")),
                    "k_pct": self._fmt_pct(sv.get("k_pct_temp")),
                    "bbk": sv.get("bbk_temp"),
                    "iso": sv.get("iso_temp"),
                    "babip": sv.get("babip_temp"),
                    "wraa": sv.get("wraa_temp"),
                    "woba": sv.get("woba_temp"),
                    "wrc_plus": sv.get("wrc_plus_temp"),
                },
            ],
        }

    def _construir_tabla_ultimos_dias(
        self, local: str, sl: Dict, visit: str, sv: Dict
    ) -> Dict:
        """Tabla C: como llegan en L10, L7, L5, L3, L1 (5 filas por equipo)"""
        filas = []
        for equipo, stats in [(local, sl), (visit, sv)]:
            for ventana in [10, 7, 5, 3, 1]:
                filas.append({
                    "equipo": equipo,
                    "ventana": f"L{ventana}",
                    "ops": stats.get(f"ops_l{ventana}"),
                    "iso": stats.get(f"iso_l{ventana}"),
                    "babip": stats.get(f"babip_l{ventana}"),
                    "wraa": stats.get(f"wraa_l{ventana}"),
                    "woba": stats.get(f"woba_l{ventana}"),
                    "wrc_plus": stats.get(f"wrc_plus_l{ventana}"),
                })
        return {
            "titulo": "COMO LLEGAN EN LOS ÚLTIMOS DÍAS",
            "filas": filas,
        }

    def _construir_tabla_bullpenes(
        self, local: str, bl: Dict, visit: str, bv: Dict
    ) -> Dict:
        """Tabla D: bullpenes en últimos 5 juegos"""
        return {
            "titulo": "BULLPENES (Últimos 5 juegos)",
            "filas": [
                {
                    "equipo": local,
                    "ip": bl.get("ip_l5"),
                    "era": bl.get("era_l5"),
                    "whip": bl.get("whip_l5"),
                    "avg_permitido": bl.get("avg_permitido_l5"),
                    "k_9": bl.get("k_9_l5"),
                    "bb_9": bl.get("bb_9_l5"),
                    "hr_9": bl.get("hr_9_l5"),
                    "fip": bl.get("fip_l5"),
                },
                {
                    "equipo": visit,
                    "ip": bv.get("ip_l5"),
                    "era": bv.get("era_l5"),
                    "whip": bv.get("whip_l5"),
                    "avg_permitido": bv.get("avg_permitido_l5"),
                    "k_9": bv.get("k_9_l5"),
                    "bb_9": bv.get("bb_9_l5"),
                    "hr_9": bv.get("hr_9_l5"),
                    "fip": bv.get("fip_l5"),
                },
            ],
        }

    def _formatear_analisis(self, a: Dict) -> Dict:
        """Formatea el análisis de filtros para el listín"""
        filtros_pasados = []
        for i in range(1, 11):
            if a.get(f"f{i}"):
                filtros_pasados.append(f"F{i}")

        return {
            "favorito": a.get("equipo_favorecido"),
            "rival": a.get("equipo_rival"),
            "total_filtros": a.get("total_filtros_pasados", 0),
            "filtros_pasados": filtros_pasados,
            "diferenciales": {
                "woba_diff": a.get("woba_diff"),
                "wrc_plus_diff": a.get("wrc_plus_diff"),
                "ops_diff": a.get("ops_diff"),
                "wraa_diff": a.get("wraa_diff"),
                "bbk_diff": a.get("bbk_diff"),
                "iso_diff": a.get("iso_diff"),
            },
            "alertas": a.get("alertas", []),
            "rebote_rival": a.get("rebote_tecnico_rival", False),
            "caliente_rival": a.get("rival_zona_caliente", False),
            "pick": a.get("pick_recomendado"),
            "mercado": a.get("mercado_recomendado"),
            "confianza": a.get("nivel_confianza"),
        }

    # ========================= TABLAS GLOBALES =========================

    def _construir_tabla_filtros(self, bloques: List[Dict]) -> Dict:
        """Construye la tabla resumen de filtros: para cada juego, qué equipo pasa cada filtro"""
        filas = []
        for b in bloques:
            a = b.get("analisis")
            if not a:
                # Juego sin análisis
                filas.append({
                    "partido": b["matchup"],
                    "F1": "", "F2": "", "F3": "", "F4": "", "F5": "",
                    "F6": "", "F7": "", "F8": "", "F9": "", "F10": "",
                    "total": "0/10",
                })
                continue

            favorito = a["favorito"]
            fila = {"partido": b["matchup"]}
            for i in range(1, 11):
                fname = f"F{i}"
                fila[fname] = favorito if fname in a["filtros_pasados"] else ""
            fila["total"] = f"{a['total_filtros']}/10"
            filas.append(fila)

        return {
            "titulo": "FILTROS APLICADOS - GANADORES SEGÚN ESTADÍSTICAS",
            "filas": filas,
        }

    def _construir_picks(self, bloques: List[Dict]) -> Dict:
        """
        Construye los picks recomendados según las reglas del tipster:
        - 8-10 filtros: directa del día (ML)
        - 6-7 filtros: candidato a combinación
        - 4-5 filtros: solo run line / colchón
        - 0-3 filtros: NO BET o ver rebote
        """
        directas = []
        combinacion_principal = []
        combinacion_secundaria = []
        run_lines = []
        no_bets = []

        for b in bloques:
            a = b.get("analisis")
            if not a:
                continue

            total = a["total_filtros"]
            item = {
                "matchup": b["matchup"],
                "hora_et": b["hora_et"],
                "favorito": a["favorito"],
                "filtros_pasados": total,
                "filtros_lista": a["filtros_pasados"],
                "pick": a["pick"],
                "mercado": a["mercado"],
                "confianza": a["confianza"],
                "alertas": a["alertas"],
            }

            if total >= config.UMBRAL_DIRECTA:  # 8+
                directas.append(item)
            elif total >= config.UMBRAL_COMBINACION:  # 6-7
                combinacion_principal.append(item)
            elif total >= config.UMBRAL_COLCHON:  # 4-5
                combinacion_secundaria.append(item)
                run_lines.append(item)
            else:
                no_bets.append(item)

        # Ordenar directas por filtros descendente (la mejor primera)
        directas.sort(key=lambda x: x["filtros_pasados"], reverse=True)

        return {
            "directa_del_dia": directas[0] if directas else None,
            "todas_las_directas": directas,
            "combinacion_principal": combinacion_principal,
            "combinacion_secundaria": combinacion_secundaria,
            "run_lines_alternativas": run_lines,
            "no_bets": no_bets,
            "resumen": {
                "total_directas": len(directas),
                "total_combinaciones": len(combinacion_principal),
                "total_alternativas": len(combinacion_secundaria),
                "total_no_bets": len(no_bets),
            },
        }

    def _obtener_efectividad_filtros(self) -> List[Dict]:
        """Obtiene la efectividad histórica de cada filtro"""
        try:
            data = db.select("efectividad_filtros")
            return sorted(data, key=lambda x: x.get("filtro", ""))
        except Exception:
            return []

    # ========================= UTILIDADES =========================

    @staticmethod
    def _fmt_pct(valor):
        """Formatea decimal a porcentaje"""
        if valor is None:
            return None
        try:
            return f"{float(valor) * 100:.1f}%"
        except Exception:
            return None

    # ========================= GUARDAR =========================

    def save_json(self, listin: Dict, target_date: date = None) -> Path:
        """Guarda el listín como JSON"""
        if target_date is None:
            target_date = get_today_et()
        filename = f"listin_{target_date.isoformat()}.json"
        filepath = self.output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(listin, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"💾 Listín JSON guardado: {filepath}")
        return filepath

    def save_html(self, listin: Dict, target_date: date = None) -> Path:
        """Guarda el listín como HTML visual estilo tipster"""
        if target_date is None:
            target_date = get_today_et()
        filename = f"listin_{target_date.isoformat()}.html"
        filepath = self.output_dir / filename

        html = self._generar_html(listin)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"💾 Listín HTML guardado: {filepath}")
        return filepath

    def save_to_supabase(self, listin: Dict, target_date: date = None):
        """Guarda el listín en Supabase para que el frontend lo lea"""
        if target_date is None:
            target_date = get_today_et()
        try:
            db.upsert(
                "listines_diarios",
                {
                    "fecha": target_date.isoformat(),
                    "contenido": listin,
                    "generado_en": datetime.now().isoformat(),
                },
                on_conflict="fecha",
            )
            logger.info(f"💾 Listín guardado en Supabase para {target_date}")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo guardar listín en Supabase: {e}")

    # ========================= GENERAR HTML =========================

    def _generar_html(self, listin: Dict) -> str:
        """Genera HTML visual del listín estilo tipster"""
        meta = listin["metadata"]
        fecha = meta["fecha_display"]

        # Picks recomendados arriba
        picks = listin["picks"]
        directa = picks.get("directa_del_dia")

        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>PicksProMLB - Listín {fecha}</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0f1419; color: #e6e6e6; margin: 0; padding: 20px; }}
  .container {{ max-width: 1400px; margin: 0 auto; }}
  h1 {{ color: #4ade80; border-bottom: 2px solid #4ade80; padding-bottom: 10px; }}
  h2 {{ color: #60a5fa; margin-top: 30px; }}
  h3 {{ color: #fbbf24; }}
  .pick-destacado {{ background: linear-gradient(135deg, #166534 0%, #16a34a 100%); padding: 20px; border-radius: 12px; margin: 20px 0; }}
  .pick-destacado h2 {{ color: white; margin-top: 0; }}
  .juego-card {{ background: #1f2937; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #60a5fa; }}
  .juego-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }}
  .juego-titulo {{ font-size: 1.4em; font-weight: bold; color: #4ade80; }}
  .juego-meta {{ color: #94a3b8; font-size: 0.95em; }}
  table {{ width: 100%; border-collapse: collapse; margin: 10px 0; background: #0f1419; }}
  th {{ background: #374151; padding: 8px; text-align: left; font-size: 0.85em; color: #9ca3af; text-transform: uppercase; }}
  td {{ padding: 8px; border-bottom: 1px solid #374151; font-size: 0.9em; }}
  .filtro-pasa {{ background: #166534; color: white; font-weight: bold; text-align: center; }}
  .filtro-no {{ background: #1f2937; color: #6b7280; text-align: center; }}
  .alerta {{ background: #7c2d12; color: #fed7aa; padding: 8px; border-radius: 4px; margin: 5px 0; font-size: 0.9em; }}
  .badge {{ display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 0.85em; font-weight: bold; }}
  .badge-alta {{ background: #16a34a; color: white; }}
  .badge-media {{ background: #ca8a04; color: white; }}
  .badge-baja {{ background: #ea580c; color: white; }}
  .badge-no {{ background: #6b7280; color: white; }}
  .seccion {{ margin: 15px 0; }}
  .seccion-titulo {{ color: #fbbf24; font-weight: bold; font-size: 1.05em; margin-bottom: 8px; }}
</style>
</head>
<body>
<div class="container">
<h1>⚾ LISTÍN MLB — {fecha}</h1>
<p class="juego-meta">Generado: {meta['generado_en'][:19].replace('T', ' ')} | {meta['total_juegos']} juegos</p>
"""

        # Picks destacados
        if directa:
            html += f"""
<div class="pick-destacado">
<h2>🎯 DIRECTA DEL DÍA</h2>
<p style="font-size: 1.3em; margin: 5px 0;"><strong>{directa['favorito']}</strong> a ganar — {directa['matchup']} ({directa['hora_et']})</p>
<p>Filtros pasados: <strong>{directa['filtros_pasados']}/10</strong> ({', '.join(directa['filtros_lista'])})</p>
<p>Pick: {directa['pick']} | Mercado: {directa['mercado']} | Confianza: <span class="badge badge-alta">ALTA</span></p>
</div>
"""

        # Combinación principal
        if picks["combinacion_principal"]:
            html += '<h2>💎 COMBINACIÓN PRINCIPAL</h2><ul>'
            for c in picks["combinacion_principal"]:
                html += f'<li><strong>{c["favorito"]}</strong> ({c["matchup"]} · {c["hora_et"]}) - {c["filtros_pasados"]}/10 filtros</li>'
            html += '</ul>'

        # Run lines alternativas
        if picks["run_lines_alternativas"]:
            html += '<h2>🛡️ RUN LINES (con colchón)</h2><ul>'
            for c in picks["run_lines_alternativas"]:
                html += f'<li><strong>{c["favorito"]}</strong> RL +1.5 ({c["matchup"]} · {c["hora_et"]}) - {c["filtros_pasados"]}/10 filtros</li>'
            html += '</ul>'

        # Tabla resumen de filtros
        html += '<h2>📊 RESUMEN DE FILTROS APLICADOS</h2>'
        html += '<table><thead><tr><th>Partido</th>'
        for i in range(1, 11):
            html += f'<th>F{i}</th>'
        html += '<th>Total</th></tr></thead><tbody>'
        for fila in listin["tabla_filtros"]["filas"]:
            html += f'<tr><td><strong>{fila["partido"]}</strong></td>'
            for i in range(1, 11):
                v = fila[f"F{i}"]
                cls = "filtro-pasa" if v else "filtro-no"
                html += f'<td class="{cls}">{v or "—"}</td>'
            html += f'<td><strong>{fila["total"]}</strong></td></tr>'
        html += '</tbody></table>'

        # Cada juego con sus 4 tablas
        html += '<h2>🏟️ ANÁLISIS POR JUEGO</h2>'
        for j in listin["juegos"]:
            html += self._html_juego(j)

        # Efectividad de filtros
        if listin["efectividad_filtros"]:
            html += '<h2>📈 EFECTIVIDAD HISTÓRICA DE FILTROS</h2>'
            html += '<table><thead><tr><th>#</th><th>Filtro</th><th>Casos</th><th>Ganados</th><th>%</th></tr></thead><tbody>'
            for f in listin["efectividad_filtros"]:
                html += f'<tr><td>{f.get("filtro")}</td><td>{f.get("descripcion", "")}</td><td>{f.get("total_casos", 0)}</td><td>{f.get("total_ganados", 0)}</td><td><strong>{f.get("porcentaje_efectividad", 0)}%</strong></td></tr>'
            html += '</tbody></table>'

        html += '</div></body></html>'
        return html

    def _html_juego(self, j: Dict) -> str:
        """HTML de un juego individual con sus 4 tablas"""
        a = j.get("analisis")
        confianza_html = ""
        if a:
            badge_cls = {
                "alta": "badge-alta", "media": "badge-media",
                "baja": "badge-baja", "no_bet": "badge-no",
            }.get(a.get("confianza", "no_bet"), "badge-no")
            confianza_html = f'<span class="badge {badge_cls}">{a["confianza"].upper()}</span>'

        html = f"""
<div class="juego-card">
<div class="juego-header">
<div class="juego-titulo">{j["matchup"]} — {j["hora_et"]}</div>
<div>{confianza_html}</div>
</div>
<div class="juego-meta">{j["estadio"]} | Pitcher Local: {j["pitcher_local"]} | Pitcher Visit: {j["pitcher_visitante"]}</div>
"""

        # Análisis y pick
        if a:
            html += f"""
<div class="seccion">
<div class="seccion-titulo">📌 Pick recomendado</div>
<p><strong>{a["favorito"]}</strong> | {a["pick"]} ({a["mercado"]}) — <strong>{a["total_filtros"]}/10 filtros</strong></p>
<p>Filtros: {", ".join(a["filtros_pasados"]) or "ninguno"}</p>
</div>
"""
            if a["alertas"]:
                html += '<div class="seccion"><div class="seccion-titulo">⚠️ Alertas</div>'
                for alerta in a["alertas"]:
                    html += f'<div class="alerta">{alerta}</div>'
                html += '</div>'

        # Tabla últimos días (la más útil)
        html += '<div class="seccion"><div class="seccion-titulo">📊 Últimos días (cómo llegan)</div>'
        html += '<table><thead><tr><th>Equipo</th><th>Vent.</th><th>OPS</th><th>ISO</th><th>BABIP</th><th>wRAA</th><th>wOBA</th><th>wRC+</th></tr></thead><tbody>'
        for f in j["tabla_ultimos_dias"]["filas"]:
            html += f'<tr><td><strong>{f["equipo"]}</strong></td><td>{f["ventana"]}</td><td>{f["ops"] or "—"}</td><td>{f["iso"] or "—"}</td><td>{f["babip"] or "—"}</td><td>{f["wraa"] or "—"}</td><td>{f["woba"] or "—"}</td><td>{f["wrc_plus"] or "—"}</td></tr>'
        html += '</tbody></table></div>'

        # Tabla bullpens
        html += '<div class="seccion"><div class="seccion-titulo">⚾ Bullpens (últimos 5 juegos)</div>'
        html += '<table><thead><tr><th>Equipo</th><th>IP</th><th>ERA</th><th>WHIP</th><th>AVG</th><th>K/9</th><th>BB/9</th><th>HR/9</th></tr></thead><tbody>'
        for f in j["tabla_bullpenes"]["filas"]:
            html += f'<tr><td><strong>{f["equipo"]}</strong></td><td>{f["ip"] or "—"}</td><td>{f["era"] or "—"}</td><td>{f["whip"] or "—"}</td><td>{f["avg_permitido"] or "—"}</td><td>{f["k_9"] or "—"}</td><td>{f["bb_9"] or "—"}</td><td>{f["hr_9"] or "—"}</td></tr>'
        html += '</tbody></table></div>'

        html += '</div>'
        return html


def run(target_date: date = None):
    """Genera y guarda el listín del día"""
    builder = ListinBuilder()
    listin = builder.build(target_date)
    if listin:
        builder.save_json(listin, target_date)
        builder.save_html(listin, target_date)
        builder.save_to_supabase(listin, target_date)
    return listin


if __name__ == "__main__":
    run()
