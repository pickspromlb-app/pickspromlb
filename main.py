"""
PicksProMLB - Orquestador Principal
Coordina todos los módulos y ejecuta el scheduler dinámico
"""

import asyncio
from datetime import date, datetime, timedelta
from typing import Optional
import pytz
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from app.utils.config import config
from app.utils.database import db
from app.collectors.calendar_collector import CalendarCollector
from app.collectors.team_stats_collector import TeamStatsCollector
from app.collectors.odds_collector import OddsCollector
from app.collectors.weather_collector import WeatherCollector
from app.engine.filter_engine import FilterEngine
from app.exports.json_builder import ListinJSONBuilder
from app.agent.gemini_agent import GeminiAgent
from app.bot.telegram_bot import PicksProBot


class PicksProOrchestrator:
    """Orquestador principal del sistema"""
    
    def __init__(self):
        self.tz = pytz.timezone(config.TIMEZONE)
        self.scheduler = AsyncIOScheduler(timezone=self.tz)
        
        self.calendar = CalendarCollector()
        self.stats = TeamStatsCollector()
        self.odds = OddsCollector()
        self.weather = WeatherCollector()
        self.engine = FilterEngine()
        self.builder = ListinJSONBuilder()
        self.agent = GeminiAgent()
        self.bot = PicksProBot()
    
    # ========== TAREAS PROGRAMADAS ==========
    
    async def task_morning(self):
        """
        Tarea matutina (7 AM ET):
        1. Procesa resultados del día anterior
        2. Actualiza histórico de filtros
        3. Detecta horarios de hoy y programa los demás triggers
        """
        logger.info("🌅 === TAREA MATUTINA INICIADA ===")
        
        try:
            # 1. Procesar resultados de ayer
            ayer = date.today() - timedelta(days=1)
            await self._procesar_resultados(ayer)
            
            # 2. Actualizar histórico de filtros
            await self._actualizar_historico_filtros()
            
            # 3. Obtener calendario de hoy
            hoy = date.today()
            games = self.calendar.get_games_for_date(hoy)
            self.calendar.save_to_db(games)
            
            if not games:
                logger.info("📅 No hay juegos hoy")
                return
            
            # 4. Detectar primer y último juego
            primer_juego, ultimo_juego = self.calendar.get_first_and_last_game_times(hoy)
            
            if not primer_juego:
                logger.warning("⚠️ No se pudo determinar hora del primer juego")
                return
            
            # 5. Programar los demás triggers basados en horarios reales
            self._programar_triggers_dinamicos(primer_juego, ultimo_juego)
            
            logger.info(f"✅ Tarea matutina completada. Primer juego: {primer_juego}, último: {ultimo_juego}")
            
            # Log
            db.insert("log_ejecuciones", {
                "fecha": hoy.isoformat(),
                "tipo": "task_morning",
                "estado": "exito",
                "mensaje": f"{len(games)} juegos programados"
            })
        except Exception as e:
            logger.error(f"❌ Error en tarea matutina: {e}")
            db.insert("log_ejecuciones", {
                "fecha": date.today().isoformat(),
                "tipo": "task_morning",
                "estado": "error",
                "mensaje": str(e)
            })
    
    async def task_generar_listin(self):
        """
        Generar listín completo (4 horas antes del primer juego):
        1. Recolecta stats actualizadas de todos los equipos
        2. Recolecta odds
        3. Recolecta clima
        4. Aplica filtros
        5. Genera JSON
        6. Analiza con Gemini
        7. Envía picks por Telegram
        """
        logger.info("📊 === GENERANDO LISTÍN COMPLETO ===")
        
        try:
            # 1. Recolectar stats
            logger.info("1/7 Recolectando stats de equipos...")
            self.stats.collect_for_all_teams()
            
            # 2. Recolectar odds
            logger.info("2/7 Recolectando odds...")
            self.odds.update_db(self.odds.parse_odds(self.odds.fetch_odds()))
            
            # 3. Recolectar clima
            logger.info("3/7 Recolectando clima...")
            juegos_hoy = db.select("juegos", filters={"fecha": date.today().isoformat()})
            self.weather.update_games_with_weather(juegos_hoy)
            
            # 4. Aplicar filtros
            logger.info("4/7 Aplicando filtros...")
            self.engine.analizar_dia()
            
            # 5. Generar JSON del listín
            logger.info("5/7 Generando JSON del listín...")
            listin = self.builder.build()
            self.builder.save(listin)
            
            # 6. Analizar con Gemini
            logger.info("6/7 Analizando con Gemini...")
            analisis = self.agent.analizar_listin(listin)
            self.agent.guardar_picks(analisis)
            
            # 7. Enviar picks por Telegram
            logger.info("7/7 Enviando picks por Telegram...")
            await self._enviar_picks_a_telegram(analisis)
            
            logger.info("✅ Listín generado y enviado")
            
            db.insert("log_ejecuciones", {
                "fecha": date.today().isoformat(),
                "tipo": "task_generar_listin",
                "estado": "exito",
                "mensaje": f"{len(listin.get('juegos', []))} juegos analizados"
            })
        except Exception as e:
            logger.error(f"❌ Error generando listín: {e}")
            db.insert("log_ejecuciones", {
                "fecha": date.today().isoformat(),
                "tipo": "task_generar_listin",
                "estado": "error",
                "mensaje": str(e)
            })
    
    async def task_actualizar_picks(self):
        """
        Actualizar picks (1 hora antes del primer juego):
        - Verifica si las odds cambiaron significativamente
        - Confirma pitchers (a veces los cambian de último minuto)
        - Re-evalúa picks si algo cambió
        """
        logger.info("🔄 === ACTUALIZANDO PICKS ===")
        
        try:
            # Actualizar odds
            self.odds.update_db(self.odds.parse_odds(self.odds.fetch_odds()))
            
            # Actualizar calendario (puede haber cambios de pitchers)
            games = self.calendar.get_games_for_date()
            self.calendar.save_to_db(games)
            
            # Re-aplicar filtros
            self.engine.analizar_dia()
            
            # Re-generar listín y picks (opcional, puede consumir cuota Gemini)
            # listin = self.builder.build()
            # analisis = self.agent.analizar_listin(listin)
            # await self._enviar_picks_a_telegram(analisis, prefijo="🔄 *ACTUALIZACIÓN:* ")
            
            logger.info("✅ Picks actualizados")
        except Exception as e:
            logger.error(f"❌ Error actualizando picks: {e}")
    
    async def task_resultados(self):
        """
        Procesar resultados (2 horas después del último juego):
        - Jala resultados finales
        - Marca picks como ganados/perdidos
        - Envía resumen por Telegram
        """
        logger.info("📊 === PROCESANDO RESULTADOS DEL DÍA ===")
        
        try:
            hoy = date.today()
            await self._procesar_resultados(hoy)
            
            # Enviar resumen por Telegram
            await self._enviar_resumen_dia(hoy)
            
            logger.info("✅ Resultados procesados")
        except Exception as e:
            logger.error(f"❌ Error procesando resultados: {e}")
    
    # ========== MÉTODOS AUXILIARES ==========
    
    async def _procesar_resultados(self, target_date: date):
        """Jala resultados finales y marca picks"""
        logger.info(f"📊 Procesando resultados de {target_date}")
        
        # Obtener juegos finalizados
        games = self.calendar.get_games_for_date(target_date)
        finalizados = [g for g in games if g.get("estado") == "finalizado"]
        
        for game in finalizados:
            try:
                # Actualizar resultado en juegos
                db.update(
                    "juegos",
                    {
                        "resultado_local": game.get("resultado_local"),
                        "resultado_visitante": game.get("resultado_visitante"),
                        "total_carreras": (game.get("resultado_local", 0) or 0) + (game.get("resultado_visitante", 0) or 0),
                        "ganador": game["equipo_local"] if game.get("resultado_local", 0) > game.get("resultado_visitante", 0) else game["equipo_visitante"],
                        "estado": "finalizado",
                    },
                    {
                        "fecha": target_date.isoformat(),
                        "equipo_local": game["equipo_local"],
                        "equipo_visitante": game["equipo_visitante"],
                    }
                )
                
                # Marcar picks como ganados/perdidos
                await self._marcar_resultado_pick(game, target_date)
                
            except Exception as e:
                logger.error(f"❌ Error procesando {game.get('equipo_local')} vs {game.get('equipo_visitante')}: {e}")
    
    async def _marcar_resultado_pick(self, game: dict, target_date: date):
        """Marca el resultado de un pick basado en el resultado real del juego"""
        local = game["equipo_local"]
        visit = game["equipo_visitante"]
        score_local = game.get("resultado_local", 0)
        score_visit = game.get("resultado_visitante", 0)
        
        # Buscar análisis del juego
        analisis = db.select(
            "filtros_aplicados",
            filters={"fecha": target_date.isoformat(), "equipo_favorecido": local}
        )
        if not analisis:
            analisis = db.select(
                "filtros_aplicados",
                filters={"fecha": target_date.isoformat(), "equipo_favorecido": visit}
            )
        
        if not analisis:
            return
        
        a = analisis[0]
        favorito = a["equipo_favorecido"]
        
        # Determinar si ganó (lógica simple: el favorito ganó el juego)
        if favorito == local:
            gano = score_local > score_visit
        else:
            gano = score_visit > score_local
        
        db.update(
            "filtros_aplicados",
            {"resultado_pick": gano},
            {
                "fecha": target_date.isoformat(),
                "equipo_favorecido": favorito,
                "equipo_rival": local if favorito == visit else visit,
            }
        )
    
    async def _actualizar_historico_filtros(self):
        """Actualiza la efectividad de cada filtro basado en histórico real"""
        logger.info("📊 Actualizando histórico de filtros...")
        
        client = db.get_client()
        
        for filtro_id in [f"f{i}" for i in range(1, 11)]:
            try:
                # Total de casos donde este filtro pasó
                response = client.table("filtros_aplicados") \
                    .select("*") \
                    .eq(filtro_id, True) \
                    .not_.is_("resultado_pick", "null") \
                    .execute()
                
                data = response.data
                total = len(data)
                ganados = sum(1 for d in data if d.get("resultado_pick") is True)
                
                if total > 0:
                    efectividad = round((ganados / total) * 100, 2)
                    db.update(
                        "efectividad_filtros",
                        {
                            "total_casos": total,
                            "total_ganados": ganados,
                            "porcentaje_efectividad": efectividad,
                            "fecha_ultima_actualizacion": date.today().isoformat(),
                        },
                        {"filtro": filtro_id.upper()}
                    )
            except Exception as e:
                logger.warning(f"⚠️ Error actualizando {filtro_id}: {e}")
    
    async def _enviar_picks_a_telegram(self, analisis: dict, prefijo: str = ""):
        """Envía los picks generados al chat de Telegram"""
        if not config.TELEGRAM_CHAT_ID:
            logger.warning("⚠️ TELEGRAM_CHAT_ID no configurado")
            return
        
        try:
            picks_hoy = db.select("picks_diarios", filters={"fecha": date.today().isoformat()})
            await self.bot.enviar_picks_automatico(picks_hoy, mensaje_extra=prefijo)
        except Exception as e:
            logger.error(f"❌ Error enviando picks: {e}")
    
    async def _enviar_resumen_dia(self, target_date: date):
        """Envía resumen del día con resultados"""
        if not config.TELEGRAM_CHAT_ID:
            return
        
        try:
            client = db.get_client()
            response = client.table("filtros_aplicados") \
                .select("*") \
                .eq("fecha", target_date.isoformat()) \
                .not_.is_("resultado_pick", "null") \
                .execute()
            
            data = response.data
            ganados = sum(1 for p in data if p.get("resultado_pick") is True)
            perdidos = sum(1 for p in data if p.get("resultado_pick") is False)
            total = ganados + perdidos
            efectividad = (ganados / total * 100) if total > 0 else 0
            
            mensaje = f"""
📊 *RESUMEN DEL DÍA - {target_date.strftime('%d/%m/%Y')}*

✅ Ganados: {ganados}
❌ Perdidos: {perdidos}
📈 Efectividad: *{efectividad:.1f}%*

Total picks evaluados: {total}
"""
            await self.bot.app.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=mensaje,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"❌ Error enviando resumen: {e}")
    
    def _programar_triggers_dinamicos(self, primer_juego: datetime, ultimo_juego: datetime):
        """
        Programa los triggers basados en los horarios REALES de los juegos.
        Esto es lo que resuelve el problema de horarios fijos.
        """
        # Convertir a timezone local
        primer = primer_juego.astimezone(self.tz)
        ultimo = ultimo_juego.astimezone(self.tz)
        
        # Trigger 1: Generar listín (4 horas antes del primer juego)
        hora_listin = primer - timedelta(hours=config.HOURS_BEFORE_FIRST_GAME)
        
        # Trigger 2: Actualizar picks (1 hora antes del primer juego)
        hora_actualizar = primer - timedelta(hours=config.HOURS_BEFORE_UPDATE)
        
        # Trigger 3: Procesar resultados (2 horas después del último juego)
        hora_resultados = ultimo + timedelta(hours=config.HOURS_AFTER_LAST_GAME)
        
        # Eliminar triggers anteriores del día
        for job in self.scheduler.get_jobs():
            if job.id in ["generar_listin_hoy", "actualizar_picks_hoy", "resultados_hoy"]:
                self.scheduler.remove_job(job.id)
        
        # Programar nuevos triggers
        if hora_listin > datetime.now(self.tz):
            self.scheduler.add_job(
                self.task_generar_listin,
                trigger=DateTrigger(run_date=hora_listin),
                id="generar_listin_hoy",
                replace_existing=True,
            )
            logger.info(f"📅 Listín se generará a las {hora_listin.strftime('%H:%M')}")
        else:
            # Si ya pasó la hora, generar ahora
            asyncio.create_task(self.task_generar_listin())
        
        if hora_actualizar > datetime.now(self.tz):
            self.scheduler.add_job(
                self.task_actualizar_picks,
                trigger=DateTrigger(run_date=hora_actualizar),
                id="actualizar_picks_hoy",
                replace_existing=True,
            )
            logger.info(f"🔄 Picks se actualizarán a las {hora_actualizar.strftime('%H:%M')}")
        
        if hora_resultados > datetime.now(self.tz):
            self.scheduler.add_job(
                self.task_resultados,
                trigger=DateTrigger(run_date=hora_resultados),
                id="resultados_hoy",
                replace_existing=True,
            )
            logger.info(f"📊 Resultados se procesarán a las {hora_resultados.strftime('%H:%M')}")
    
    def iniciar_scheduler(self):
        """Inicia el scheduler con la tarea matutina diaria"""
        # Tarea matutina diaria a las 7:00 AM ET
        self.scheduler.add_job(
            self.task_morning,
            trigger=CronTrigger(hour=7, minute=0, timezone=self.tz),
            id="morning_task",
            replace_existing=True,
        )
        
        self.scheduler.start()
        logger.info("⏰ Scheduler iniciado")
        logger.info("   📅 Tarea matutina: 7:00 AM ET diariamente")
    
    async def ejecutar_manual(self, fecha: date = None):
        """Ejecuta TODO el flujo manualmente para una fecha (útil para testing)"""
        if fecha is None:
            fecha = date.today()
        
        logger.info(f"🚀 Ejecución manual completa para {fecha}")
        
        # 1. Calendario
        games = self.calendar.get_games_for_date(fecha)
        self.calendar.save_to_db(games)
        
        # 2. Stats
        self.stats.collect_for_all_teams(fecha)
        
        # 3. Odds
        self.odds.update_db(self.odds.parse_odds(self.odds.fetch_odds()))
        
        # 4. Clima
        juegos = db.select("juegos", filters={"fecha": fecha.isoformat()})
        self.weather.update_games_with_weather(juegos)
        
        # 5. Filtros
        self.engine.analizar_dia(fecha)
        
        # 6. Listín JSON
        listin = self.builder.build(fecha)
        self.builder.save(listin, fecha)
        
        # 7. Análisis Gemini
        analisis = self.agent.analizar_listin(listin)
        self.agent.guardar_picks(analisis, fecha)
        
        # 8. Enviar a Telegram
        await self._enviar_picks_a_telegram(analisis)
        
        logger.info(f"✅ Ejecución manual completada para {fecha}")
        return analisis


async def main():
    """Función principal: inicia el sistema en modo daemon"""
    logger.info("🎯 === PICKSPROMLB INICIANDO ===")
    
    # Validar configuración
    if not config.validar():
        logger.error("❌ Configuración inválida, no se puede iniciar")
        return
    
    orchestrator = PicksProOrchestrator()
    
    # Iniciar scheduler
    orchestrator.iniciar_scheduler()
    
    # Ejecutar tarea matutina inmediatamente al arrancar (para detectar juegos de hoy)
    await orchestrator.task_morning()
    
    # Iniciar bot de Telegram en paralelo
    logger.info("🤖 Iniciando bot de Telegram...")
    
    # Mantener el sistema corriendo
    try:
        # Bot polling
        await orchestrator.bot.app.initialize()
        await orchestrator.bot.app.start()
        await orchestrator.bot.app.updater.start_polling()
        
        logger.info("✅ Sistema corriendo. Presiona Ctrl+C para detener.")
        
        # Mantener vivo
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        logger.info("⏹️ Sistema detenido por usuario")
    finally:
        await orchestrator.bot.app.updater.stop()
        await orchestrator.bot.app.stop()
        await orchestrator.bot.app.shutdown()
        orchestrator.scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
