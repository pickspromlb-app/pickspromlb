"""
PicksProMLB - Calculador de Estadísticas Sabermétricas (v2 con caché)
================================================================
ESTE ARCHIVO YA NO LLAMA A LA API DE MLB.
Lee los juegos pre-cargados de historico_juegos_equipos y CALCULA
las ventanas L1, L3, L5, L7, L10 con stats sabermétricas reales.

Es ULTRA RÁPIDO (segundos en vez de minutos).
"""

from datetime import date
from typing import Dict, List, Optional
from loguru import logger

from app.utils.database import db
from app.utils.config import config
from app.utils.time_utils import get_today_et
from app.collectors.historico_collector import HistoricoCollector


# Constantes wOBA 2024 (oficiales FanGraphs)
WOBA_WEIGHTS = {
    "BB": 0.696,
    "HBP": 0.726,
    "1B": 0.886,
    "2B": 1.261,
    "3B": 1.601,
    "HR": 2.072,
}

# wOBA y wRC+ de la liga (2024-2025)
LEAGUE_WOBA = 0.318
LEAGUE_WRC = 4.28
WOBA_SCALE = 1.157


class TeamStatsCollector:
    """Calcula stats sabermétricas POR VENTANA leyendo de la BD"""

    def __init__(self):
        self.windows = [1, 3, 5, 7, 10]
        self.historico = HistoricoCollector()

    # ========================= AGREGACIÓN =========================

    def _aggregate_games(self, games: List[Dict]) -> Dict:
        """Agrega stats acumuladas de N juegos"""
        if not games:
            return {}

        agg = {
            "g": len(games),
            "ab": sum(g.get("ab", 0) for g in games),
            "r": sum(g.get("r", 0) for g in games),
            "h": sum(g.get("h", 0) for g in games),
            "doubles": sum(g.get("doubles", 0) for g in games),
            "triples": sum(g.get("triples", 0) for g in games),
            "hr": sum(g.get("hr", 0) for g in games),
            "rbi": sum(g.get("rbi", 0) for g in games),
            "bb": sum(g.get("bb", 0) for g in games),
            "so": sum(g.get("so", 0) for g in games),
            "hbp": sum(g.get("hbp", 0) for g in games),
            "sf": sum(g.get("sf", 0) for g in games),
            "pa": sum(g.get("pa", 0) for g in games),
        }
        # Singles = H - 2B - 3B - HR
        agg["singles"] = agg["h"] - agg["doubles"] - agg["triples"] - agg["hr"]
        # ⚾ FIX BUG SLG: TB DEBE calcularse desde hits, no leerse de la caché.
        # La API MLB no devuelve totalBases a nivel equipo, por eso TB salía en 0
        # y SLG se calculaba como 0, y OPS = OBP, y los filtros F2/F4/F7/F8 nunca activaban.
        # Fórmula oficial MLB: TB = 1B + 2*2B + 3*3B + 4*HR
        agg["tb"] = agg["singles"] + (2 * agg["doubles"]) + (3 * agg["triples"]) + (4 * agg["hr"])
        return agg

    def _aggregate_bullpen(self, games: List[Dict]) -> Dict:
        """Agrega stats del bullpen de N juegos"""
        if not games:
            return {}
        return {
            "bp_ip_outs": sum(g.get("bp_ip_outs", 0) for g in games),
            "bp_h": sum(g.get("bp_h", 0) for g in games),
            "bp_r": sum(g.get("bp_r", 0) for g in games),
            "bp_er": sum(g.get("bp_er", 0) for g in games),
            "bp_bb": sum(g.get("bp_bb", 0) for g in games),
            "bp_so": sum(g.get("bp_so", 0) for g in games),
            "bp_hr": sum(g.get("bp_hr", 0) for g in games),
            "bp_hbp": sum(g.get("bp_hbp", 0) for g in games),
            "bp_tbf": sum(g.get("bp_tbf", 0) for g in games),
        }

    # ========================= STATS BÁSICAS =========================

    def _calc_basic_stats(self, agg: Dict) -> Dict:
        """Calcula AVG, OBP, SLG, OPS, ISO, BABIP, BB%, K%, BB/K"""
        ab = agg.get("ab", 0)
        h = agg.get("h", 0)
        bb = agg.get("bb", 0)
        hbp = agg.get("hbp", 0)
        sf = agg.get("sf", 0)
        tb = agg.get("tb", 0)
        so = agg.get("so", 0)
        hr = agg.get("hr", 0)
        pa = agg.get("pa", 0) or (ab + bb + hbp + sf)

        avg = h / ab if ab > 0 else 0.0
        obp = (h + bb + hbp) / pa if pa > 0 else 0.0
        slg = tb / ab if ab > 0 else 0.0
        ops = obp + slg
        iso = slg - avg
        babip_denom = ab - so - hr + sf
        babip = (h - hr) / babip_denom if babip_denom > 0 else 0.0
        bb_pct = bb / pa if pa > 0 else 0.0
        k_pct = so / pa if pa > 0 else 0.0
        bbk = bb / so if so > 0 else 0.0

        return {
            "avg": round(avg, 4),
            "obp": round(obp, 4),
            "slg": round(slg, 4),
            "ops": round(ops, 4),
            "iso": round(iso, 4),
            "babip": round(babip, 4),
            "bb_pct": round(bb_pct, 4),
            "k_pct": round(k_pct, 4),
            "bbk": round(bbk, 2),
        }

    def _calc_advanced_stats(self, agg: Dict) -> Dict:
        """Calcula wOBA, wRAA, wRC, wRC+"""
        bb = agg.get("bb", 0)
        hbp = agg.get("hbp", 0)
        singles = agg.get("singles", 0)
        doubles = agg.get("doubles", 0)
        triples = agg.get("triples", 0)
        hr = agg.get("hr", 0)
        ab = agg.get("ab", 0)
        sf = agg.get("sf", 0)
        pa = agg.get("pa", 0) or (ab + bb + hbp + sf)

        # wOBA
        woba_denom = ab + bb + sf + hbp
        if woba_denom > 0:
            woba_num = (
                WOBA_WEIGHTS["BB"] * bb
                + WOBA_WEIGHTS["HBP"] * hbp
                + WOBA_WEIGHTS["1B"] * singles
                + WOBA_WEIGHTS["2B"] * doubles
                + WOBA_WEIGHTS["3B"] * triples
                + WOBA_WEIGHTS["HR"] * hr
            )
            woba = woba_num / woba_denom
        else:
            woba = 0.0

        # wRAA = ((wOBA - lgWOBA) / wOBAScale) * PA
        wraa = ((woba - LEAGUE_WOBA) / WOBA_SCALE) * pa if pa > 0 else 0.0

        # wRC+ aproximado
        league_r_per_pa = LEAGUE_WRC / 38.0
        if league_r_per_pa > 0:
            wrc_per_pa = (woba - LEAGUE_WOBA) / WOBA_SCALE + league_r_per_pa
            wrc_plus = round((wrc_per_pa / league_r_per_pa) * 100)
            wrc = round(wrc_per_pa * pa) if pa > 0 else 0
        else:
            wrc_plus = 100
            wrc = 0

        return {
            "woba": round(woba, 4),
            "wraa": round(wraa, 2),
            "wrc": wrc,
            "wrc_plus": wrc_plus,
        }

    def _calc_bullpen_stats(self, agg: Dict) -> Dict:
        """Calcula ERA, WHIP, FIP, etc del bullpen"""
        ip = agg.get("bp_ip_outs", 0) / 3.0
        if ip == 0:
            return {}

        h = agg.get("bp_h", 0)
        r = agg.get("bp_r", 0)
        er = agg.get("bp_er", 0)
        bb = agg.get("bp_bb", 0)
        so = agg.get("bp_so", 0)
        hr = agg.get("bp_hr", 0)
        hbp = agg.get("bp_hbp", 0)
        tbf = agg.get("bp_tbf", 0)
        ab_approx = tbf - bb - hbp

        era = (er * 9) / ip if ip > 0 else 0
        whip = (bb + h) / ip if ip > 0 else 0
        avg_perm = h / ab_approx if ab_approx > 0 else 0
        k_9 = (so * 9) / ip if ip > 0 else 0
        bb_9 = (bb * 9) / ip if ip > 0 else 0
        hr_9 = (hr * 9) / ip if ip > 0 else 0
        k_bb = so / bb if bb > 0 else so
        k_pct = so / tbf if tbf > 0 else 0
        bb_pct = bb / tbf if tbf > 0 else 0
        # FIP simplificado
        fip = (
            ((13 * hr + 3 * (bb + hbp) - 2 * so) / ip + 3.10) if ip > 0 else 0
        )

        return {
            "ip": round(ip, 1),
            "era": round(era, 2),
            "whip": round(whip, 2),
            "avg_permitido": round(avg_perm, 3),
            "k_9": round(k_9, 1),
            "bb_9": round(bb_9, 1),
            "hr_9": round(hr_9, 1),
            "k_bb": round(k_bb, 2),
            "k_pct": round(k_pct, 4),
            "bb_pct": round(bb_pct, 4),
            "fip": round(fip, 2),
            "tbf": tbf,
        }

    # ========================= RECOLECCIÓN PRINCIPAL =========================

    def _jugo_en_coors(self, games: List[Dict]) -> bool:
        """Detecta si los últimos 3 juegos fueron en Coors Field"""
        if not games:
            return False
        for g in games[:3]:
            estadio = g.get("estadio", "")
            if "Coors" in estadio:
                return True
        return False

    def collect_for_team(self, team_abbr: str, target_date: date = None) -> Dict:
        """
        Calcula stats por ventana LEYENDO DE LA BD (no llama API).
        Es ULTRA RÁPIDO.
        """
        if target_date is None:
            target_date = get_today_et()

        # Leer últimos 10 juegos del equipo desde la BD
        games = self.historico.get_juegos_equipo(team_abbr, num_games=10)

        if not games:
            logger.warning(
                f"⚠️ {team_abbr}: sin datos en caché. Ejecuta /cargar_historico primero."
            )
            return {}

        result = {
            "fecha": target_date.isoformat(),
            "equipo": team_abbr,
            "jugo_en_coors": self._jugo_en_coors(games),
        }

        # Calcular para cada ventana
        for window in self.windows:
            window_games = games[:window]
            if not window_games:
                continue

            # Bateo
            agg = self._aggregate_games(window_games)
            basic = self._calc_basic_stats(agg)
            advanced = self._calc_advanced_stats(agg)

            result[f"avg_l{window}"] = basic["avg"]
            result[f"obp_l{window}"] = basic["obp"]
            result[f"slg_l{window}"] = basic["slg"]
            result[f"ops_l{window}"] = basic["ops"]
            result[f"iso_l{window}"] = basic["iso"]
            result[f"babip_l{window}"] = basic["babip"]
            result[f"bb_pct_l{window}"] = basic["bb_pct"]
            result[f"k_pct_l{window}"] = basic["k_pct"]
            result[f"bbk_l{window}"] = basic["bbk"]
            result[f"woba_l{window}"] = advanced["woba"]
            result[f"wraa_l{window}"] = advanced["wraa"]
            result[f"wrc_l{window}"] = advanced["wrc"]
            result[f"wrc_plus_l{window}"] = advanced["wrc_plus"]
            result[f"juegos_l{window}"] = agg["g"]
            result[f"carreras_l{window}"] = agg["r"]

        # Stats de "temporada" (todos los juegos en caché)
        all_agg = self._aggregate_games(games)
        all_basic = self._calc_basic_stats(all_agg)
        all_advanced = self._calc_advanced_stats(all_agg)
        result["avg_temp"] = all_basic["avg"]
        result["obp_temp"] = all_basic["obp"]
        result["slg_temp"] = all_basic["slg"]
        result["ops_temp"] = all_basic["ops"]
        result["iso_temp"] = all_basic["iso"]
        result["babip_temp"] = all_basic["babip"]
        result["bb_pct_temp"] = all_basic["bb_pct"]
        result["k_pct_temp"] = all_basic["k_pct"]
        result["bbk_temp"] = all_basic["bbk"]
        result["woba_temp"] = all_advanced["woba"]
        result["wraa_temp"] = all_advanced["wraa"]
        result["wrc_plus_temp"] = all_advanced["wrc_plus"]

        # Bullpen últimos 5 juegos
        bp_agg = self._aggregate_bullpen(games[:5])
        bp_stats = self._calc_bullpen_stats(bp_agg)
        if bp_stats:
            result["bullpen_l5"] = bp_stats

        logger.info(
            f"✅ {team_abbr}: AVG={all_basic['avg']:.3f} OPS={all_basic['ops']:.3f} "
            f"wOBA={all_advanced['woba']:.3f} wRC+={all_advanced['wrc_plus']}"
        )
        return result

    def collect_for_all_teams(self, target_date: date = None) -> List[Dict]:
        """Calcula stats de los 30 equipos LEYENDO de BD (rápido)"""
        if target_date is None:
            target_date = get_today_et()

        logger.info("📊 === CALCULANDO STATS DE LOS 30 EQUIPOS (desde caché) ===")

        all_stats = []
        all_bullpens = []

        for team_abbr in config.EQUIPOS_MLB.keys():
            try:
                stats = self.collect_for_team(team_abbr, target_date)
                if stats:
                    # Separar bullpen
                    bp_stats = stats.pop("bullpen_l5", None)
                    all_stats.append(stats)

                    if bp_stats:
                        bp_record = {
                            "fecha": target_date.isoformat(),
                            "equipo": team_abbr,
                            "ip_l5": bp_stats["ip"],
                            "tbf_l5": bp_stats["tbf"],
                            "era_l5": bp_stats["era"],
                            "whip_l5": bp_stats["whip"],
                            "avg_permitido_l5": bp_stats["avg_permitido"],
                            "k_9_l5": bp_stats["k_9"],
                            "bb_9_l5": bp_stats["bb_9"],
                            "hr_9_l5": bp_stats["hr_9"],
                            "k_bb_l5": bp_stats["k_bb"],
                            "k_pct_l5": bp_stats["k_pct"],
                            "bb_pct_l5": bp_stats["bb_pct"],
                            "fip_l5": bp_stats["fip"],
                        }
                        all_bullpens.append(bp_record)
            except Exception as e:
                logger.error(f"❌ Error con {team_abbr}: {e}")
                continue

        # Guardar en BD
        if all_stats:
            self.save_to_db(all_stats)
        if all_bullpens:
            self.save_bullpens_to_db(all_bullpens)

        logger.info(
            f"✅ Stats: {len(all_stats)}/30 | Bullpens: {len(all_bullpens)}/30"
        )
        return all_stats

    def save_to_db(self, team_stats: List[Dict]) -> int:
        """Guarda en equipos_diario"""
        saved = 0
        for stats in team_stats:
            try:
                db.upsert("equipos_diario", stats, on_conflict="fecha,equipo")
                saved += 1
            except Exception as e:
                logger.error(
                    f"❌ Error guardando stats {stats.get('equipo')}: {e}"
                )
        logger.info(f"💾 {saved}/{len(team_stats)} stats guardadas")
        return saved

    def save_bullpens_to_db(self, bullpens: List[Dict]) -> int:
        """Guarda en bullpenes_diario"""
        saved = 0
        for bp in bullpens:
            try:
                db.upsert("bullpenes_diario", bp, on_conflict="fecha,equipo")
                saved += 1
            except Exception as e:
                logger.error(f"❌ Error guardando bullpen {bp.get('equipo')}: {e}")
        logger.info(f"💾 {saved}/{len(bullpens)} bullpens guardados")
        return saved


def run():
    collector = TeamStatsCollector()
    return collector.collect_for_all_teams()


if __name__ == "__main__":
    run()
