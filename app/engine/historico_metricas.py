"""
PicksProMLB - Histórico Acumulado de Métricas
Replica el método del tipster: para cada métrica, calcula cuántas veces los equipos
con cierto rango produjeron 3+ carreras. Estos porcentajes son el corazón del análisis.

Ejemplo: "Cuando wOBA L5 > 0.400, el 78% de las veces el equipo hace 3+ carreras"

Mantiene 3 ventanas temporales (como el tipster):
- HISTÓRICO: desde inicio de temporada
- VENTANA_500: últimos ~500 equipos-juegos
- VENTANA_RECIENTE: últimos ~125 equipos-juegos (~2 semanas)
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger

from app.utils.database import db
from app.utils.time_utils import get_today_et


# Definición de rangos para cada métrica (alineados con el tipster)
RANGOS_METRICAS = {
    "avg_l5": [
        {"nombre": "rebote_extremo", "min": 0.000, "max": 0.150, "tipo": "rebote"},
        {"nombre": "bajo", "min": 0.150, "max": 0.200, "tipo": "neutral"},
        {"nombre": "promedio", "min": 0.200, "max": 0.270, "tipo": "neutral"},
        {"nombre": "bueno", "min": 0.270, "max": 0.300, "tipo": "neutral"},
        {"nombre": "muy_bueno", "min": 0.300, "max": 0.350, "tipo": "caliente"},
        {"nombre": "elite", "min": 0.350, "max": 1.000, "tipo": "caliente"},
    ],
    "obp_l5": [
        {"nombre": "muy_bajo", "min": 0.000, "max": 0.250, "tipo": "rebote"},
        {"nombre": "bajo", "min": 0.250, "max": 0.300, "tipo": "neutral"},
        {"nombre": "promedio", "min": 0.300, "max": 0.350, "tipo": "neutral"},
        {"nombre": "bueno", "min": 0.350, "max": 0.400, "tipo": "neutral"},
        {"nombre": "elite", "min": 0.400, "max": 1.000, "tipo": "caliente"},
    ],
    "slg_l5": [
        {"nombre": "rebote_extremo", "min": 0.000, "max": 0.300, "tipo": "rebote"},
        {"nombre": "bajo", "min": 0.300, "max": 0.380, "tipo": "neutral"},
        {"nombre": "promedio", "min": 0.380, "max": 0.450, "tipo": "neutral"},
        {"nombre": "bueno", "min": 0.450, "max": 0.500, "tipo": "neutral"},
        {"nombre": "muy_bueno", "min": 0.500, "max": 0.600, "tipo": "caliente"},
        {"nombre": "elite", "min": 0.600, "max": 2.000, "tipo": "caliente"},
    ],
    "ops_l5": [
        {"nombre": "muy_bajo", "min": 0.000, "max": 0.550, "tipo": "rebote"},
        {"nombre": "bajo", "min": 0.550, "max": 0.650, "tipo": "neutral"},
        {"nombre": "promedio", "min": 0.650, "max": 0.750, "tipo": "neutral"},
        {"nombre": "bueno", "min": 0.750, "max": 0.850, "tipo": "neutral"},
        {"nombre": "muy_bueno", "min": 0.850, "max": 0.950, "tipo": "caliente"},
        {"nombre": "elite", "min": 0.950, "max": 3.000, "tipo": "caliente"},
    ],
    "iso_l5": [
        {"nombre": "muy_bajo", "min": 0.000, "max": 0.080, "tipo": "neutral"},
        {"nombre": "bajo", "min": 0.080, "max": 0.130, "tipo": "neutral"},
        {"nombre": "promedio", "min": 0.130, "max": 0.180, "tipo": "neutral"},
        {"nombre": "bueno", "min": 0.180, "max": 0.250, "tipo": "neutral"},
        {"nombre": "elite", "min": 0.250, "max": 1.000, "tipo": "caliente"},
    ],
    "babip_l5": [
        {"nombre": "muy_bajo", "min": 0.000, "max": 0.220, "tipo": "rebote"},
        {"nombre": "bajo", "min": 0.220, "max": 0.270, "tipo": "neutral"},
        {"nombre": "promedio", "min": 0.270, "max": 0.330, "tipo": "neutral"},
        {"nombre": "bueno", "min": 0.330, "max": 0.400, "tipo": "neutral"},
        {"nombre": "elite", "min": 0.400, "max": 1.000, "tipo": "caliente"},
    ],
    "woba_l5": [
        {"nombre": "muy_bajo", "min": 0.000, "max": 0.260, "tipo": "rebote"},
        {"nombre": "bajo", "min": 0.260, "max": 0.300, "tipo": "neutral"},
        {"nombre": "promedio", "min": 0.300, "max": 0.340, "tipo": "neutral"},
        {"nombre": "bueno", "min": 0.340, "max": 0.380, "tipo": "neutral"},
        {"nombre": "muy_bueno", "min": 0.380, "max": 0.400, "tipo": "caliente"},
        {"nombre": "elite", "min": 0.400, "max": 1.000, "tipo": "caliente"},
    ],
    "wrc_plus_l5": [
        {"nombre": "rebote_extremo", "min": -100, "max": 50, "tipo": "rebote"},
        {"nombre": "bajo", "min": 50, "max": 80, "tipo": "neutral"},
        {"nombre": "promedio", "min": 80, "max": 110, "tipo": "neutral"},
        {"nombre": "bueno", "min": 110, "max": 140, "tipo": "neutral"},
        {"nombre": "elite", "min": 140, "max": 500, "tipo": "caliente"},
    ],
    "bb_pct_l5": [
        {"nombre": "muy_bajo", "min": 0.000, "max": 0.050, "tipo": "neutral"},
        {"nombre": "bajo", "min": 0.050, "max": 0.080, "tipo": "neutral"},
        {"nombre": "promedio", "min": 0.080, "max": 0.110, "tipo": "neutral"},
        {"nombre": "alto", "min": 0.110, "max": 0.150, "tipo": "caliente"},
        {"nombre": "muy_alto", "min": 0.150, "max": 1.000, "tipo": "caliente"},
    ],
    "k_pct_l5": [
        {"nombre": "elite", "min": 0.000, "max": 0.150, "tipo": "caliente"},
        {"nombre": "bajo", "min": 0.150, "max": 0.180, "tipo": "neutral"},
        {"nombre": "promedio", "min": 0.180, "max": 0.230, "tipo": "neutral"},
        {"nombre": "alto", "min": 0.230, "max": 0.280, "tipo": "neutral"},
        {"nombre": "muy_alto", "min": 0.280, "max": 1.000, "tipo": "rebote"},
    ],
}


class HistoricoMetricas:
    """
    Calcula y mantiene el histórico de cada métrica.
    Para cada combinación (métrica, rango, ventana_temporal) calcula:
      - Total de equipos-juegos en ese rango
      - Cuántos hicieron 3+ carreras
      - Cuántos hicieron 5+ carreras
      - % de probabilidad
    """

    VENTANAS_TEMPORALES = {
        "historico": None,         # desde inicio temporada
        "ultimos_500": 500,        # últimos 500 equipos-juegos
        "ultimos_125": 125,        # últimos 125 equipos-juegos (~2 semanas)
    }

    def __init__(self):
        pass

    def actualizar_historico(self) -> Dict:
        """
        Actualiza la tabla historico_metricas con todos los datos disponibles.
        Usa los juegos finalizados con resultados conocidos.
        """
        logger.info("📊 === ACTUALIZANDO HISTÓRICO DE MÉTRICAS ===")

        # Obtener todos los equipos-juegos con resultados conocidos
        # JOIN entre equipos_diario (stats) y juegos (resultados)
        registros = self._obtener_registros_completos()

        if not registros:
            logger.warning("⚠️ No hay registros completos para análisis histórico")
            return {}

        logger.info(f"📊 Procesando {len(registros)} equipos-juegos con resultados")

        resultados = {}

        # Para cada métrica
        for metrica, rangos in RANGOS_METRICAS.items():
            resultados[metrica] = {}

            # Para cada ventana temporal
            for nombre_ventana, limite in self.VENTANAS_TEMPORALES.items():
                if limite:
                    registros_ventana = registros[:limite]
                else:
                    registros_ventana = registros

                if not registros_ventana:
                    continue

                # Para cada rango
                for rango in rangos:
                    en_rango = [
                        r for r in registros_ventana
                        if r.get(metrica) is not None
                        and rango["min"] <= r[metrica] < rango["max"]
                    ]

                    total = len(en_rango)
                    if total == 0:
                        continue

                    hicieron_3 = sum(1 for r in en_rango if r.get("carreras", 0) >= 3)
                    hicieron_5 = sum(1 for r in en_rango if r.get("carreras", 0) >= 5)

                    pct_3 = round((hicieron_3 / total) * 100, 1)
                    pct_5 = round((hicieron_5 / total) * 100, 1)

                    registro = {
                        "metrica": metrica,
                        "ventana_temporal": nombre_ventana,
                        "rango_nombre": rango["nombre"],
                        "rango_min": rango["min"],
                        "rango_max": rango["max"],
                        "tipo": rango["tipo"],
                        "total_casos": total,
                        "casos_3plus": hicieron_3,
                        "casos_5plus": hicieron_5,
                        "porcentaje_3plus": pct_3,
                        "porcentaje_5plus": pct_5,
                        "fecha_actualizacion": get_today_et().isoformat(),
                    }

                    resultados[metrica].setdefault(nombre_ventana, []).append(registro)

                    # Guardar en BD
                    try:
                        db.upsert(
                            "historico_metricas",
                            registro,
                            on_conflict="metrica,ventana_temporal,rango_nombre",
                        )
                    except Exception as e:
                        logger.debug(f"No se pudo guardar histórico: {e}")

        logger.info(f"✅ Histórico actualizado para {len(resultados)} métricas")
        return resultados

    def _obtener_registros_completos(self) -> List[Dict]:
        """
        Obtiene todos los equipos-juegos con stats Y resultado conocido.
        Devuelve lista ordenada del más reciente al más viejo.
        """
        try:
            # Tomamos juegos finalizados
            juegos = db.select("juegos", filters={"estado": "finalizado"})
        except Exception as e:
            logger.error(f"Error obteniendo juegos finalizados: {e}")
            return []

        registros = []
        for juego in juegos:
            fecha = juego.get("fecha")
            if not fecha:
                continue

            # Para cada equipo del juego, buscar sus stats de ese día
            for lado in ["local", "visitante"]:
                equipo = juego.get(f"equipo_{lado}")
                carreras = juego.get(f"resultado_{lado}")

                if not equipo or carreras is None:
                    continue

                stats_list = db.select(
                    "equipos_diario", filters={"fecha": fecha, "equipo": equipo}
                )
                if not stats_list:
                    continue

                stats = stats_list[0]
                registro = dict(stats)
                registro["carreras"] = carreras
                registro["fecha_juego"] = fecha
                registros.append(registro)

        # Ordenar por fecha descendente
        registros.sort(key=lambda r: r.get("fecha_juego", ""), reverse=True)
        return registros

    def consultar_probabilidad(
        self,
        metrica: str,
        valor: float,
        ventana: str = "historico",
    ) -> Optional[Dict]:
        """
        Para un valor dado de una métrica, devuelve la probabilidad de hacer 3+ y 5+ carreras.
        Útil cuando estamos analizando un equipo y queremos saber su probabilidad esperada.
        """
        rangos = RANGOS_METRICAS.get(metrica)
        if not rangos:
            return None

        # Encontrar el rango donde cae el valor
        rango_match = None
        for r in rangos:
            if r["min"] <= valor < r["max"]:
                rango_match = r
                break

        if not rango_match:
            return None

        # Buscar en BD
        try:
            data = db.select(
                "historico_metricas",
                filters={
                    "metrica": metrica,
                    "ventana_temporal": ventana,
                    "rango_nombre": rango_match["nombre"],
                },
            )
        except Exception:
            return None

        if not data:
            return None

        return {
            "metrica": metrica,
            "valor": valor,
            "rango": rango_match["nombre"],
            "tipo": rango_match["tipo"],
            "porcentaje_3plus": data[0].get("porcentaje_3plus"),
            "porcentaje_5plus": data[0].get("porcentaje_5plus"),
            "muestra": data[0].get("total_casos"),
            "ventana": ventana,
        }

    def analizar_equipo(self, stats_equipo: Dict) -> Dict:
        """
        Para un equipo, analiza todas sus métricas L5 contra el histórico.
        Devuelve probabilidades de carreras según cada métrica.
        """
        analisis = {
            "metricas_calientes": [],
            "metricas_rebote": [],
            "probabilidad_3plus_promedio": 0,
            "probabilidad_5plus_promedio": 0,
            "detalles": {},
        }

        prob_3_acum = []
        prob_5_acum = []

        for metrica in RANGOS_METRICAS.keys():
            valor = stats_equipo.get(metrica)
            if valor is None:
                continue

            prob = self.consultar_probabilidad(metrica, valor, "historico")
            if not prob:
                continue

            analisis["detalles"][metrica] = prob

            if prob["tipo"] == "caliente":
                analisis["metricas_calientes"].append({
                    "metrica": metrica,
                    "valor": valor,
                    "rango": prob["rango"],
                    "prob_3plus": prob["porcentaje_3plus"],
                })
            elif prob["tipo"] == "rebote":
                analisis["metricas_rebote"].append({
                    "metrica": metrica,
                    "valor": valor,
                    "rango": prob["rango"],
                    "prob_3plus": prob["porcentaje_3plus"],
                })

            if prob["porcentaje_3plus"]:
                prob_3_acum.append(prob["porcentaje_3plus"])
            if prob["porcentaje_5plus"]:
                prob_5_acum.append(prob["porcentaje_5plus"])

        if prob_3_acum:
            analisis["probabilidad_3plus_promedio"] = round(sum(prob_3_acum) / len(prob_3_acum), 1)
        if prob_5_acum:
            analisis["probabilidad_5plus_promedio"] = round(sum(prob_5_acum) / len(prob_5_acum), 1)

        return analisis


def run():
    """Actualiza el histórico de métricas"""
    h = HistoricoMetricas()
    return h.actualizar_historico()


if __name__ == "__main__":
    run()
