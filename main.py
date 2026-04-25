"""
PicksProMLB - Orquestador v2.1 (con correcciones críticas)
================================================================
ARQUITECTURA INTELIGENTE con caché:
- Carga inicial: UNA sola vez (~30 min) vía /cargar_historico
- Cada mañana 7 AM ET: solo actualiza juegos del día anterior (~5 min)
- /analizar: lee de caché + filtros + listín (<1 min)

CORRECCIONES INCLUIDAS (v2.1):
1. ✅ get_today_et() en lugar de date.today() (bug de zona horaria a las 11pm)
2. ✅ Validar primer_juego/ultimo_juego antes de programar triggers
3. ✅ get_games_for_date(fecha) consistente (siempre con parámetro)
4. ✅ Evaluador de picks soporta ML, RL +1.5/+2.5, F5, Over/Under, Team Total
5. ✅ Resultados de picks van a picks_diarios; filtros_aplicados solo mide filtros
6. ✅ Protección contra listín duplicado (no regenerar si ya existe)
"""

import asyncio
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict
import pytz
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from app.utils.config import config
from app.utils.database import db
from app.utils.time_utils import get_today_et, get_yesterday_et, get_now_et
from app.utils.pick_evaluator import evaluate_pick_result, parse_tipo_pick

from app.collectors.calendar_collector import CalendarCollector
from app.collectors.historico_collector import HistoricoCollector
from app.collectors.team_stats_collector import TeamStatsCollector
from app.collectors.odds_collector import OddsCollector
from app.collectors.weather_collector import WeatherCollector
from app.engine.filter_engine import FilterEngine
from app.engine.historico_metricas import HistoricoMetricas
from app.exports.listin_builder import ListinBuilder
from app.exports.json_builder import ListinJSONBuilder
from app.agent.gemini_agent import GeminiAgent
from app.bot.telegram_bot import PicksProBot


class PicksProOrchestrator:
    """Orquestador principal v2.1"""

    def __init__(self):
        self.tz = pytz.timezone(config.TIMEZONE)
        self.scheduler = AsyncIOScheduler(timezone=self.tz)

        self.calendar = CalendarCollector()
        self.historico_col = HistoricoCollector()
        self.stats = TeamStatsCollector()
        self.odds = OddsCollector()
        self.weather = WeatherCollector()
        self.engine = FilterEngine()
        self.historico_metricas = HistoricoMetricas()
        self.builder_listin = ListinBuilder()
        self.builder_json = ListinJSONBuilder()
        self.agent = GeminiAgent()
        self.bot = PicksProBot()
        self.bot.orchestrator = self

    # ========================= TAREA MATUTINA (7 AM ET) =========================

    async def task_morning(self):
        """
        Tarea matutina diaria (7 AM ET):
        1. Procesa resultados del día anterior + evalúa picks
        2. Actualiza histórico de juegos (solo ayer, ~5 min)
        3. Actualiza histórico de filtros + métricas
        4. Programa triggers del día
        """
        logger.info("🌅 === TAREA MATUTINA INICIADA ===")
        try:
            # FIX #1: Usar zona ET en lugar de date.today()
            ayer = get_yesterday_et()
            hoy = get_today_et()

            # 1. Procesar resultados de ayer (jala scores + actualiza juegos)
            await self._procesar_resultados(ayer)

            # FIX #5: Evaluar picks de ayer y guardar resultados en picks_diarios
            await self._evaluar_picks_dia(ayer)

            # 2. Actualizar caché histórico (solo ayer)
            try:
                resumen = self.historico_col.actualizar_ayer()
                logger.info(f"📦 Caché actualizada: {resumen}")
            except Exception as e:
                logger.warning(f"No se pudo actualizar histórico: {e}")

            # 3. Actualizar histórico de filtros + métricas
            await self._actualizar_historico_filtros()
            try:
                self.historico_metricas.actualizar_historico()
            except Exception as e:
                logger.warning(f"No se pudo actualizar métricas: {e}")

            # 4. Calendario de hoy (FIX #3: pasar fecha explícita)
            games = self.calendar.get_games_for_date(hoy)
            saved = self.calendar.save_to_db(games)
            logger.info(f"💾 Juegos del día guardados: {saved}")

            if not games:
                logger.info("📅 No hay juegos hoy")
                self._registrar_log(hoy, "task_morning", "exito", "Sin juegos hoy")
                return

            # 5. Programar triggers (FIX #2: validar None)
            primer_juego, ultimo_juego = self.calendar.get_first_and_last_game_times(hoy)
            self._programar_triggers_dinamicos(primer_juego, ultimo_juego)

            self._registrar_log(
                hoy, "task_morning", "exito",
                f"{len(games)} juegos | Caché actualizada",
            )
        except Exception as e:
            logger.error(f"❌ Error tarea matutina: {e}")
            self._registrar_log(get_today_et(), "task_morning", "error", str(e))

    # ========================= GENERAR LISTÍN =========================

    async def task_generar_listin(self):
        """Llamado automáticamente 4h antes del primer juego"""
        await self._generar_listin_completo(automatico=True)

    async def task_generar_listin_manual(self):
        """Llamado desde /analizar en Telegram (forzar regeneración)"""
        await self._generar_listin_completo(automatico=False, forzar=True)

    async def _generar_listin_completo(self, automatico: bool = True, forzar: bool = False):
        """
        Pipeline RÁPIDO (lee de caché):
        1. Validar juegos del día
        2. FIX #6: Verificar si ya hay listín generado (no duplicar)
        3. Calcular stats por ventana (LEE de caché, instantáneo)
        4. Recolectar odds + clima
        5. Aplicar filtros
        6. Generar listín
        7. Llamar Gemini (opcional)
        """
        modo = "AUTOMÁTICO" if automatico else "MANUAL (/analizar)"
        logger.info(f"📊 === GENERANDO LISTÍN ({modo}) ===")
        # FIX #1: usar zona ET
        hoy = get_today_et()
        fecha_str = hoy.isoformat()

        try:
            # 1. Validar juegos en BD
            juegos_hoy = db.select("juegos", filters={"fecha": fecha_str})
            if not juegos_hoy:
                logger.warning("⚠️ Sin juegos en BD. Recolectando...")
                # FIX #3: pasar fecha explícita
                games = self.calendar.get_games_for_date(hoy)
                self.calendar.save_to_db(games)
                juegos_hoy = db.select("juegos", filters={"fecha": fecha_str})
                if not juegos_hoy:
                    logger.error("❌ Sin juegos. Abortando.")
                    self._registrar_log(hoy, "task_generar_listin", "error", "Sin juegos")
                    return

            # FIX #6: protección contra listín duplicado
            if not forzar:
                existing = db.select("listines_diarios", filters={"fecha": fecha_str})
                if existing:
                    logger.info(
                        f"⚠️ Listín del {fecha_str} ya existe. "
                        f"Omitiendo generación (usar forzar=True para regenerar)."
                    )
                    self._registrar_log(
                        hoy, "task_generar_listin", "omitido",
                        "Listín ya existe, no se regeneró",
                    )
                    return

            logger.info(f"📋 Procesando {len(juegos_hoy)} juegos")

            # 2. Calcular stats por ventana DESDE CACHÉ (rápido)
            logger.info("1/6 ⚾ Calculando stats sabermétricas desde caché...")
            stats_results = self.stats.collect_for_all_teams(hoy)
            if not stats_results:
                logger.error("❌ Sin stats. La caché podría estar vacía.")
                self._registrar_log(
                    hoy, "task_generar_listin", "error",
                    "Caché vacía. Ejecutar /cargar_historico",
                )
                return

            # 3. Odds
            logger.info("2/6 💰 Recolectando odds...")
            try:
                self.odds.update_db(self.odds.parse_odds(self.odds.fetch_odds()))
            except Exception as e:
                logger.warning(f"Error odds: {e}")

            # 4. Clima
            logger.info("3/6 🌤️ Recolectando clima...")
            try:
                juegos_hoy = db.select("juegos", filters={"fecha": fecha_str})
                self.weather.update_games_with_weather(juegos_hoy)
            except Exception as e:
                logger.warning(f"Error clima: {e}")

            # 5. Aplicar filtros
            logger.info("4/6 🎯 Aplicando los 10 filtros...")
            self.engine.analizar_dia(hoy)

            # 6. Generar listín
            logger.info("5/6 📋 Generando listín visual...")
            listin = self.builder_listin.build(hoy)
            if not listin:
                logger.warning("Listín vacío")
                return

            self.builder_listin.save_json(listin, hoy)
            self.builder_listin.save_html(listin, hoy)
            self.builder_listin.save_to_supabase(listin, hoy)

            # 7. Análisis con Gemini (opcional)
            logger.info("6/6 🧠 Análisis con Gemini...")
            try:
                listin_json = self.builder_json.build(hoy)
                analisis = self.agent.analizar_listin(listin_json)
                if analisis:
                    self.agent.guardar_picks(analisis, hoy)
            except Exception as e:
                logger.warning(f"Gemini falló (no crítico): {e}")

            logger.info("✅ Listín generado completamente")
            self._registrar_log(
                hoy, "task_generar_listin", "exito",
                f"{len(juegos_hoy)} juegos analizados",
            )

            # Notificación corta solo en modo automático
            if automatico and config.TELEGRAM_CHAT_ID:
                try:
                    picks = listin.get("picks", {})
                    directa = picks.get("directa_del_dia")
                    msg = (
                        f"✅ *Análisis del día listo*\n"
                        f"_{len(juegos_hoy)} juegos procesados_\n\n"
                    )
                    if directa:
                        msg += f"🎯 *Directa:* {directa['favorito']} ({directa['filtros_pasados']}/10)\n\n"
                    msg += "Usa /listin para ver completo o /picks para ver picks."
                    await self.bot.app.bot.send_message(
                        chat_id=config.TELEGRAM_CHAT_ID,
                        text=msg,
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.warning(f"No se pudo notificar: {e}")

        except Exception as e:
            logger.error(f"❌ Error generando listín: {e}")
            self._registrar_log(hoy, "task_generar_listin", "error", str(e))

    # ========================= ACTUALIZAR / RESULTADOS =========================

    async def task_actualizar_picks(self):
        """1h antes del primer juego: re-evaluar con odds actualizados"""
        logger.info("🔄 === ACTUALIZANDO PICKS ===")
        try:
            self.odds.update_db(self.odds.parse_odds(self.odds.fetch_odds()))
            # FIX #3: pasar fecha explícita
            hoy = get_today_et()
            games = self.calendar.get_games_for_date(hoy)
            self.calendar.save_to_db(games)
            self.engine.analizar_dia(hoy)
            logger.info("✅ Picks actualizados")
        except Exception as e:
            logger.error(f"❌ Error: {e}")

    async def task_resultados(self):
        """2h después del último juego: procesar resultados + evaluar picks"""
        logger.info("📊 === PROCESANDO RESULTADOS DEL DÍA ===")
        try:
            hoy = get_today_et()
            await self._procesar_resultados(hoy)
            # FIX #5: evaluar picks del día y guardar resultados
            await self._evaluar_picks_dia(hoy)
            logger.info("✅ Resultados procesados")
        except Exception as e:
            logger.error(f"❌ Error: {e}")

    async def _procesar_resultados(self, target_date: date):
        """Jala resultados finales y actualiza tabla 'juegos'"""
        logger.info(f"📊 Procesando resultados de {target_date}")
        # FIX #3: siempre pasar fecha explícita
        games = self.calendar.get_games_for_date(target_date)
        finalizados = [g for g in games if g.get("estado") == "finalizado"]

        for game in finalizados:
            try:
                local = game["equipo_local"]
                visit = game["equipo_visitante"]
                rl = game.get("resultado_local") or 0
                rv = game.get("resultado_visitante") or 0
                ganador = local if rl > rv else visit

                db.update(
                    "juegos",
                    {
                        "resultado_local": rl,
                        "resultado_visitante": rv,
                        "total_carreras": rl + rv,
                        "ganador": ganador,
                        "estado": "finalizado",
                    },
                    {
                        "fecha": target_date.isoformat(),
                        "equipo_local": local,
                        "equipo_visitante": visit,
                    },
                )
            except Exception as e:
                logger.error(f"❌ Error procesando juego: {e}")

    # ========================= FIX #5: EVALUACIÓN INTELIGENTE DE PICKS =========================

    async def _evaluar_picks_dia(self, target_date: date):
        """
        FIX #5: Evalúa los picks de un día usando el evaluador inteligente.
        Soporta ML, RL +1.5/+2.5/+3.5, F5, Over/Under, Team Total.
        Los resultados se guardan EN picks_diarios (no en filtros_aplicados).
        """
        logger.info(f"🎯 Evaluando picks de {target_date}")
        fecha_str = target_date.isoformat()

        # Obtener picks del día
        try:
            picks = db.select("picks_diarios", filters={"fecha": fecha_str})
        except Exception as e:
            logger.error(f"No se pudieron obtener picks: {e}")
            return

        if not picks:
            logger.info(f"Sin picks para evaluar en {target_date}")
            return

        # Obtener juegos finalizados del día
        try:
            juegos = db.select("juegos", filters={"fecha": fecha_str})
        except Exception as e:
            logger.error(f"No se pudieron obtener juegos: {e}")
            return

        # Mapeo rápido por matchup
        juegos_por_equipo = {}
        for j in juegos:
            local = j.get("equipo_local")
            visit = j.get("equipo_visitante")
            if local:
                juegos_por_equipo.setdefault(local, []).append(j)
            if visit:
                juegos_por_equipo.setdefault(visit, []).append(j)

        evaluados = 0
        ganados = 0
        perdidos = 0
        sin_evaluar = 0

        for pick in picks:
            try:
                # Si ya tiene resultado, saltarlo
                if pick.get("resultado") in ("ganado", "perdido"):
                    continue

                # Identificar equipo del pick
                juegos_data = pick.get("juegos") or []
                if not isinstance(juegos_data, list) or not juegos_data:
                    sin_evaluar += 1
                    continue

                # Para cada sub-pick (caso de combinada)
                resultados_sub = []
                for sub in juegos_data:
                    if not isinstance(sub, dict):
                        continue
                    equipo = sub.get("equipo") or sub.get("favorito")
                    if not equipo:
                        continue

                    juegos_eq = juegos_por_equipo.get(equipo, [])
                    if not juegos_eq:
                        resultados_sub.append(None)
                        continue

                    # Construir el pick formato evaluador
                    pick_eval = {
                        "tipo_pick": sub.get("tipo_pick") or pick.get("tipo_pick", "ML"),
                        "equipo": equipo,
                    }
                    juego_eq = juegos_eq[0]
                    res = evaluate_pick_result(pick_eval, juego_eq)
                    resultados_sub.append(res)

                # Determinar resultado final del pick (combinado o sencillo)
                if not resultados_sub:
                    sin_evaluar += 1
                    continue

                if any(r is None for r in resultados_sub):
                    # Algún sub-pick sin evaluar (juego no finalizado o push)
                    sin_evaluar += 1
                    continue

                resultado_final = "ganado" if all(r is True for r in resultados_sub) else "perdido"

                # FIX #5: actualizar picks_diarios con resultado
                pick_id = pick.get("id")
                if pick_id:
                    db.update(
                        "picks_diarios",
                        {
                            "resultado": resultado_final,
                            "fecha_evaluacion": get_now_et().isoformat(),
                        },
                        {"id": pick_id},
                    )
                    evaluados += 1
                    if resultado_final == "ganado":
                        ganados += 1
                    else:
                        perdidos += 1
            except Exception as e:
                logger.warning(f"Error evaluando pick {pick.get('id')}: {e}")
                continue

        logger.info(
            f"✅ Picks evaluados: {evaluados} (ganados: {ganados}, perdidos: {perdidos}, "
            f"sin evaluar: {sin_evaluar})"
        )

    async def _actualizar_historico_filtros(self):
        """
        Actualiza efectividad histórica de cada filtro.
        FIX #5: filtros_aplicados ya NO tiene resultado_pick (eso vive en picks_diarios).
        Aquí calculamos: para cada filtro, en qué % de juegos donde el filtro ESTABA ACTIVO,
        el equipo favorecido terminó GANANDO el juego.
        """
        logger.info("📊 Actualizando histórico filtros...")

        for filtro_id in [f"f{i}" for i in range(1, 11)]:
            try:
                # Obtener filtros aplicados
                client = db.get_client()
                response = (
                    client.table("filtros_aplicados")
                    .select("*")
                    .eq(filtro_id, True)
                    .execute()
                )
                filtros_data = response.data or []

                if not filtros_data:
                    continue

                # Para cada filtro aplicado, ver si el equipo favorecido ganó el juego
                total = 0
                ganados = 0

                for f in filtros_data:
                    fecha = f.get("fecha")
                    favorito = f.get("equipo_favorecido")
                    rival = f.get("equipo_rival")

                    if not (fecha and favorito and rival):
                        continue

                    # Buscar el juego correspondiente
                    juegos = db.select("juegos", filters={"fecha": fecha})
                    juego = next(
                        (
                            j
                            for j in juegos
                            if (j.get("equipo_local") == favorito and j.get("equipo_visitante") == rival)
                            or (j.get("equipo_local") == rival and j.get("equipo_visitante") == favorito)
                        ),
                        None,
                    )

                    if not juego or juego.get("estado") != "finalizado":
                        continue

                    if juego.get("resultado_local") is None or juego.get("resultado_visitante") is None:
                        continue

                    total += 1
                    rl = juego.get("resultado_local") or 0
                    rv = juego.get("resultado_visitante") or 0
                    ganador = juego.get("equipo_local") if rl > rv else juego.get("equipo_visitante")
                    if ganador == favorito:
                        ganados += 1

                if total > 0:
                    ef = round((ganados / total) * 100, 2)
                    db.update(
                        "efectividad_filtros",
                        {
                            "total_casos": total,
                            "total_ganados": ganados,
                            "porcentaje_efectividad": ef,
                            "fecha_ultima_actualizacion": get_today_et().isoformat(),
                        },
                        {"filtro": filtro_id.upper()},
                    )
            except Exception as e:
                logger.warning(f"⚠️ {filtro_id}: {e}")

    # ========================= FIX #2: TRIGGERS CON VALIDACIÓN =========================

    def _programar_triggers_dinamicos(
        self, primer_juego: Optional[datetime], ultimo_juego: Optional[datetime]
    ):
        """
        Programa triggers según horarios reales del día.
        FIX #2: Validar que primer_juego y ultimo_juego no sean None.
        """
        # FIX #2: Validación crítica
        if primer_juego is None or ultimo_juego is None:
            logger.warning(
                "⚠️ No se programan triggers: primer_juego o ultimo_juego es None "
                "(no hay juegos hoy o falta info de horario)"
            )
            return

        try:
            primer = primer_juego.astimezone(self.tz)
            ultimo = ultimo_juego.astimezone(self.tz)
        except Exception as e:
            logger.error(f"Error convirtiendo horarios a TZ: {e}")
            return

        hora_listin = primer - timedelta(hours=config.HOURS_BEFORE_FIRST_GAME)
        hora_actualizar = primer - timedelta(hours=config.HOURS_BEFORE_UPDATE)
        hora_resultados = ultimo + timedelta(hours=config.HOURS_AFTER_LAST_GAME)

        # Limpiar jobs anteriores
        for job in self.scheduler.get_jobs():
            if job.id in ["generar_listin_hoy", "actualizar_picks_hoy", "resultados_hoy"]:
                self.scheduler.remove_job(job.id)

        # FIX #1: usar get_now_et()
        ahora = get_now_et()

        if hora_listin > ahora:
            self.scheduler.add_job(
                self.task_generar_listin,
                trigger=DateTrigger(run_date=hora_listin),
                id="generar_listin_hoy",
                replace_existing=True,
            )
            logger.info(f"📅 Listín auto: {hora_listin.strftime('%H:%M')} ET")
        else:
            asyncio.create_task(self.task_generar_listin())

        if hora_actualizar > ahora:
            self.scheduler.add_job(
                self.task_actualizar_picks,
                trigger=DateTrigger(run_date=hora_actualizar),
                id="actualizar_picks_hoy",
                replace_existing=True,
            )

        if hora_resultados > ahora:
            self.scheduler.add_job(
                self.task_resultados,
                trigger=DateTrigger(run_date=hora_resultados),
                id="resultados_hoy",
                replace_existing=True,
            )

    def iniciar_scheduler(self):
        """Tarea matutina diaria 7 AM ET"""
        self.scheduler.add_job(
            self.task_morning,
            trigger=CronTrigger(hour=7, minute=0, timezone=self.tz),
            id="morning_task",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("⏰ Scheduler iniciado (7 AM ET diario)")

    # ========================= UTILIDADES =========================

    def _registrar_log(self, fecha: date, tipo: str, estado: str, mensaje: str):
        """Helper centralizado para insertar en log_ejecuciones"""
        try:
            db.insert("log_ejecuciones", {
                "fecha": fecha.isoformat(),
                "tipo": tipo,
                "estado": estado,
                "mensaje": mensaje[:500],  # truncar para no romper
            })
        except Exception as e:
            logger.debug(f"No se pudo registrar log: {e}")


async def main():
    """Función principal"""
    logger.info("🎯 === PICKSPROMLB v2.1 INICIANDO ===")

    if not config.validar():
        logger.error("❌ Configuración inválida")
        return

    orchestrator = PicksProOrchestrator()
    orchestrator.iniciar_scheduler()
    await orchestrator.task_morning()

    logger.info("🤖 Iniciando bot Telegram...")
    await asyncio.sleep(5)  # Evitar conflict

    try:
        await orchestrator.bot.app.initialize()
        await orchestrator.bot.app.start()
        await orchestrator.bot.app.updater.start_polling(drop_pending_updates=True)

        logger.info("✅ Sistema corriendo. Use /cargar_historico (1ra vez) o /analizar.")
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        logger.info("⏹️ Detenido")
    finally:
        await orchestrator.bot.app.updater.stop()
        await orchestrator.bot.app.stop()
        await orchestrator.bot.app.shutdown()
        orchestrator.scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
