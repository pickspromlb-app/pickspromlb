"""
PicksProMLB - Bot de Telegram (v2 con /cargar_historico)
Comandos disponibles:
  /start              - Bienvenida
  /ayuda              - Lista de comandos
  /cargar_historico   - PRIMERA VEZ: poblar BD con últimos 20 días (~30 min)
  /estado_cache       - Ver cuánta data hay en caché
  /analizar           - Disparar análisis del día (rápido, lee de caché)
  /listin             - Ver listín del día
  /picks              - Ver picks del día
  /juegos             - Ver juegos ordenados por hora
  /juego TEAM         - Detalle de un juego
  /filtros            - Los 10 filtros con efectividad
  /historico          - Rendimiento histórico
  /clima TEAM         - Clima del estadio
  /odds TEAM          - Cuotas del juego
"""

import asyncio
from datetime import date, datetime, timedelta
from typing import List, Dict
import pytz
from loguru import logger
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.utils.database import db
from app.utils.config import config
from app.utils.time_utils import get_today_et


class PicksProBot:
    """Bot de Telegram para PicksProMLB"""

    def __init__(self):
        if not config.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN no configurado")

        self.app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        self._registrar_handlers()
        self.orchestrator = None

    def _registrar_handlers(self):
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("ayuda", self.cmd_ayuda))
        self.app.add_handler(CommandHandler("help", self.cmd_ayuda))
        self.app.add_handler(CommandHandler("cargar_historico", self.cmd_cargar_historico))
        self.app.add_handler(CommandHandler("estado_cache", self.cmd_estado_cache))
        self.app.add_handler(CommandHandler("analizar", self.cmd_analizar))
        self.app.add_handler(CommandHandler("listin", self.cmd_listin))
        self.app.add_handler(CommandHandler("picks", self.cmd_picks))
        self.app.add_handler(CommandHandler("juegos", self.cmd_juegos))
        self.app.add_handler(CommandHandler("juego", self.cmd_juego))
        self.app.add_handler(CommandHandler("filtros", self.cmd_filtros))
        self.app.add_handler(CommandHandler("historico", self.cmd_historico))
        self.app.add_handler(CommandHandler("clima", self.cmd_clima))
        self.app.add_handler(CommandHandler("odds", self.cmd_odds))
        self.app.add_handler(CommandHandler("rendimiento", self.cmd_historico))

    # ========================= BÁSICOS =========================

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = (
            "⚾ *¡Bienvenido a PicksProMLB!*\n\n"
            "Sistema sabermétrico de análisis MLB.\n\n"
            "🔥 *PRIMERA VEZ:*\n"
            "Ejecuta `/cargar_historico` para poblar la BD con últimos 20 días.\n"
            "(Tarda ~30 min, solo se hace UNA VEZ).\n\n"
            "🎯 *USO DIARIO:*\n"
            "/analizar - Análisis del día (~1 min)\n"
            "/listin - Ver listín completo\n"
            "/picks - Picks recomendados\n"
            "/juegos - Juegos del día\n\n"
            "Escribe /ayuda para ver todos los comandos."
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_ayuda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = (
            "📋 *COMANDOS DISPONIBLES*\n\n"
            "🏗️ *Setup (primera vez)*\n"
            "/cargar_historico - Poblar BD (20 días)\n"
            "/estado_cache - Ver estado de la caché\n\n"
            "🚀 *Análisis*\n"
            "/analizar - Análisis completo del día\n"
            "/listin - Ver listín del día\n"
            "/listin AAAA-MM-DD - Listín de fecha pasada\n"
            "/picks - Picks recomendados\n\n"
            "📊 *Información*\n"
            "/juegos - Juegos del día (ordenados)\n"
            "/juego TEAM - Detalle de un juego\n"
            "/filtros - Los 10 filtros\n"
            "/historico - Rendimiento histórico\n"
            "/clima TEAM - Clima del estadio\n"
            "/odds TEAM - Cuotas del juego"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    # ========================= /cargar_historico =========================

    async def cmd_cargar_historico(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Carga inicial: jala últimos 20 días de juegos (UNA SOLA VEZ)"""
        await update.message.reply_text(
            "🏗️ *INICIANDO CARGA HISTÓRICA*\n\n"
            "Voy a poblar la BD con los últimos 20 días de juegos de los 30 equipos.\n\n"
            "⏳ *Esto tomará 30-40 minutos.*\n"
            "✅ *Solo se hace UNA VEZ en la vida del sistema.*\n\n"
            "Después de esto:\n"
            "• /analizar tardará menos de 1 minuto\n"
            "• Cada mañana se actualiza solo el día anterior (~5 min)\n\n"
            "Te aviso cuando termine.",
            parse_mode="Markdown",
        )

        if not self.orchestrator:
            await update.message.reply_text("❌ Error: orchestrator no disponible.")
            return

        asyncio.create_task(self._ejecutar_carga_historica(update.effective_chat.id))

    async def _ejecutar_carga_historica(self, chat_id: int):
        """Ejecuta carga histórica en background"""
        try:
            from app.collectors.historico_collector import HistoricoCollector
            collector = HistoricoCollector()
            resumen = collector.cargar_inicial(20)

            await self.app.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"✅ *CARGA HISTÓRICA COMPLETA*\n\n"
                    f"• Juegos guardados: *{resumen['guardados']}*\n"
                    f"• Ya existían: {resumen['ya_existian']}\n"
                    f"• Errores: {resumen['errores']}\n"
                    f"• Rango: {resumen['rango']}\n\n"
                    f"Ahora puedes usar /analizar (rápido)."
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Error en carga histórica: {e}")
            await self.app.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Error en carga histórica: {str(e)[:300]}",
            )

    # ========================= /estado_cache =========================

    async def cmd_estado_cache(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra cuántos juegos hay en caché por equipo"""
        try:
            from app.collectors.historico_collector import HistoricoCollector
            collector = HistoricoCollector()
            estado = collector.get_estado_cache()
        except Exception as e:
            await update.message.reply_text(f"❌ Error consultando caché: {e}")
            return

        if not estado:
            await update.message.reply_text(
                "📭 La caché está vacía.\n\nUsa /cargar_historico para poblarla."
            )
            return

        # Resumen
        total_juegos = sum(e["total_juegos"] for e in estado.values())
        equipos_con_data = sum(1 for e in estado.values() if e["total_juegos"] > 0)
        sin_data = [t for t, e in estado.items() if e["total_juegos"] == 0]

        msg = "📊 *ESTADO DE LA CACHÉ*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += f"✅ Equipos con data: *{equipos_con_data}/30*\n"
        msg += f"📦 Total juegos en caché: *{total_juegos}*\n"
        promedio = total_juegos / equipos_con_data if equipos_con_data else 0
        msg += f"📈 Promedio por equipo: *{promedio:.1f}* juegos\n\n"

        if sin_data:
            msg += f"⚠️ *Sin data ({len(sin_data)}):* {', '.join(sin_data[:10])}\n\n"

        # Top 5 equipos con más juegos
        top = sorted(estado.items(), key=lambda x: -x[1]["total_juegos"])[:5]
        msg += "*Top equipos con más data:*\n"
        for team, data in top:
            msg += f"• {team}: {data['total_juegos']} juegos (último: {data['ultimo_juego'] or '—'})\n"

        if equipos_con_data == 0:
            msg += "\n💡 Usa /cargar_historico para empezar."

        await update.message.reply_text(msg, parse_mode="Markdown")

    # ========================= /analizar =========================

    async def cmd_analizar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Dispara análisis del día (rápido, lee de caché)"""
        # Validar que la caché tenga datos
        try:
            from app.collectors.historico_collector import HistoricoCollector
            collector = HistoricoCollector()
            estado = collector.get_estado_cache()
            equipos_con_data = sum(1 for e in estado.values() if e["total_juegos"] > 0)
        except Exception:
            equipos_con_data = 0

        if equipos_con_data < 20:
            await update.message.reply_text(
                "⚠️ *La caché no está poblada.*\n\n"
                f"Solo hay {equipos_con_data}/30 equipos con datos.\n"
                "Ejecuta primero `/cargar_historico` (~30 min, solo 1 vez).",
                parse_mode="Markdown",
            )
            return

        await update.message.reply_text(
            "🔄 *Iniciando análisis del día...*\n\n"
            "Esto tarda 1-2 minutos:\n"
            "1️⃣ Obteniendo juegos de hoy\n"
            "2️⃣ Calculando stats desde caché (instantáneo)\n"
            "3️⃣ Recolectando odds + clima\n"
            "4️⃣ Aplicando los 10 filtros\n"
            "5️⃣ Generando listín\n\n"
            "Te aviso cuando termine.",
            parse_mode="Markdown",
        )

        if not self.orchestrator:
            await update.message.reply_text("❌ Error: orchestrator no disponible.")
            return

        asyncio.create_task(self._ejecutar_analisis(update.effective_chat.id))

    async def _ejecutar_analisis(self, chat_id: int):
        """Ejecuta el análisis en background"""
        try:
            await self.orchestrator.task_generar_listin_manual()
            await self.app.bot.send_message(
                chat_id=chat_id,
                text="✅ *Análisis completado*\n\nUsa /listin para ver el listín o /picks para los picks.",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Error en análisis: {e}")
            await self.app.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Error en el análisis: {str(e)[:300]}",
            )

    # ========================= /listin =========================

    async def cmd_listin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        target_date = get_today_et()
        if context.args:
            try:
                target_date = datetime.strptime(context.args[0], "%Y-%m-%d").date()
            except ValueError:
                await update.message.reply_text("❌ Formato: /listin AAAA-MM-DD")
                return

        try:
            data = db.select("listines_diarios", filters={"fecha": target_date.isoformat()})
        except Exception:
            data = None

        if not data:
            await update.message.reply_text(
                f"❌ No hay listín para {target_date.strftime('%d/%m/%Y')}.\n\n"
                "Usa /analizar para generarlo."
            )
            return

        listin = data[0].get("contenido", {})
        msg = self._formatear_listin(listin, target_date)
        await update.message.reply_text(msg, parse_mode="Markdown")

    def _formatear_listin(self, listin: Dict, target_date: date) -> str:
        meta = listin.get("metadata", {})
        picks = listin.get("picks", {})

        msg = f"📋 *LISTÍN MLB — {target_date.strftime('%d/%m/%Y')}*\n"
        msg += f"_{meta.get('total_juegos', 0)} juegos analizados_\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

        directa = picks.get("directa_del_dia")
        if directa:
            msg += f"🎯 *DIRECTA DEL DÍA*\n"
            msg += f"➡️ *{directa['favorito']}* a ganar\n"
            msg += f"📍 {directa['matchup']} · {directa['hora_et']}\n"
            msg += f"✅ {directa['filtros_pasados']}/10 filtros: {', '.join(directa['filtros_lista'])}\n\n"

        if picks.get("combinacion_principal"):
            msg += "💎 *COMBINACIÓN PRINCIPAL*\n"
            for c in picks["combinacion_principal"][:3]:
                msg += f"• *{c['favorito']}* ({c['matchup']} · {c['hora_et']}) — {c['filtros_pasados']}/10\n"
            msg += "\n"

        if picks.get("run_lines_alternativas"):
            msg += "🛡️ *RUN LINES (con colchón)*\n"
            for c in picks["run_lines_alternativas"][:3]:
                msg += f"• *{c['favorito']}* RL +1.5 ({c['matchup']} · {c['hora_et']})\n"
            msg += "\n"

        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "Más detalle: /juego TEAM\n"
        msg += f"Web: https://pickspromlb.vercel.app/listin/{target_date.isoformat()}"
        return msg

    # ========================= /picks =========================

    async def cmd_picks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        fecha = get_today_et().isoformat()
        try:
            picks = db.select("picks_diarios", filters={"fecha": fecha})
        except Exception:
            picks = []

        if not picks:
            await update.message.reply_text(
                "⚠️ No hay picks aún para hoy.\n\nUsa /analizar."
            )
            return

        msg = f"🎯 *PICKS DEL DÍA — {get_today_et().strftime('%d/%m/%Y')}*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

        for p in picks:
            tipo = p.get("tipo_pick", "").upper()
            cuota = p.get("cuota_total", "—")
            razon = p.get("razonamiento", "")
            juegos = p.get("juegos", [])

            msg += f"*{tipo}*"
            if cuota and cuota != "—":
                msg += f" — Cuota: {cuota}"
            msg += "\n"

            if isinstance(juegos, list):
                for j in juegos[:5]:
                    if isinstance(j, dict):
                        eq = j.get("equipo") or j.get("favorito") or "?"
                        msg += f"• {eq}\n"
                    else:
                        msg += f"• {j}\n"

            if razon:
                msg += f"_💬 {razon[:200]}_\n"
            msg += "\n"

        await update.message.reply_text(msg, parse_mode="Markdown")

    # ========================= /juegos (ORDENADO POR HORA) =========================

    async def cmd_juegos(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        fecha = get_today_et().isoformat()
        try:
            juegos = db.select("juegos", filters={"fecha": fecha})
        except Exception:
            juegos = []

        if not juegos:
            await update.message.reply_text("⚠️ No hay juegos hoy.")
            return

        et = pytz.timezone("America/New_York")

        def parse_hora(j):
            h = j.get("hora_inicio")
            if not h:
                return datetime.max
            try:
                return datetime.fromisoformat(str(h).replace("Z", "+00:00"))
            except Exception:
                return datetime.max

        juegos.sort(key=parse_hora)

        msg = f"⚾ *JUEGOS DEL DÍA — {get_today_et().strftime('%d/%m/%Y')}*\n"
        msg += "_(Ordenados por hora ET)_\n━━━━━━━━━━━━━━━━━━━━\n\n"

        for j in juegos:
            local = j.get("equipo_local", "?")
            visit = j.get("equipo_visitante", "?")
            hora_iso = j.get("hora_inicio")

            hora_str = "TBD"
            if hora_iso:
                try:
                    dt = datetime.fromisoformat(str(hora_iso).replace("Z", "+00:00"))
                    dt_et = dt.astimezone(et)
                    hora_str = dt_et.strftime("%I:%M %p ET").lstrip("0")
                except Exception:
                    pass

            msg += f"⚪️ *{visit} @ {local}* — {hora_str}\n"

        msg += f"\n_{len(juegos)} juegos_\n\nUsa /juego TEAM para detalle"
        await update.message.reply_text(msg, parse_mode="Markdown")

    # ========================= /juego TEAM =========================

    async def cmd_juego(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("❌ Indica equipo. Ej: /juego BAL")
            return

        team = context.args[0].upper()
        fecha = get_today_et().isoformat()

        try:
            juegos = db.select("juegos", filters={"fecha": fecha})
            juego = next(
                (j for j in juegos if j.get("equipo_local") == team or j.get("equipo_visitante") == team),
                None,
            )
        except Exception:
            juego = None

        if not juego:
            await update.message.reply_text(f"❌ No hay juego de {team} hoy.")
            return

        local = juego["equipo_local"]
        visit = juego["equipo_visitante"]

        analisis_list = db.select(
            "filtros_aplicados",
            filters={"fecha": fecha, "equipo_favorecido": local, "equipo_rival": visit},
        )
        if not analisis_list:
            analisis_list = db.select(
                "filtros_aplicados",
                filters={"fecha": fecha, "equipo_favorecido": visit, "equipo_rival": local},
            )

        msg = f"⚾ *{visit} @ {local}*\n"
        msg += f"📍 {juego.get('estadio', 'TBD')}\n"
        msg += f"⏰ {juego.get('hora_inicio', 'TBD')}\n"
        msg += f"🎯 {juego.get('pitcher_visitante') or 'TBD'} vs {juego.get('pitcher_local') or 'TBD'}\n\n"

        if analisis_list:
            a = analisis_list[0]
            filtros = [f"F{i}" for i in range(1, 11) if a.get(f"f{i}")]
            msg += f"📊 *Análisis:*\n"
            msg += f"Favorito: *{a.get('equipo_favorecido')}*\n"
            msg += f"Filtros: *{a.get('total_filtros_pasados', 0)}/10* ({', '.join(filtros) or 'ninguno'})\n"
            msg += f"Pick: *{a.get('pick_recomendado')}*\n"
            msg += f"Confianza: *{a.get('nivel_confianza', '').upper()}*\n\n"

            if a.get("alertas"):
                msg += "⚠️ *Alertas:*\n"
                for alerta in a["alertas"][:5]:
                    msg += f"• {alerta}\n"
        else:
            msg += "_Sin análisis. Usa /analizar._"

        await update.message.reply_text(msg, parse_mode="Markdown")

    # ========================= /filtros, /historico, /clima, /odds =========================

    async def cmd_filtros(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            efectividades = db.select("efectividad_filtros")
            efmap = {e.get("filtro"): e for e in efectividades}
        except Exception:
            efmap = {}

        msg = "📊 *LOS 10 FILTROS*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for fid, fdef in config.FILTROS.items():
            ef = efmap.get(fid, {})
            pct = ef.get("porcentaje_efectividad") or fdef.get("efectividad_base", 0)
            estrella = " ⭐" if fdef.get("es_filtro_estrella") else ""
            msg += f"*{fid}*{estrella} — *{pct}%*\n_{fdef['descripcion']}_\n\n"

        msg += "⭐ = Filtro estrella (>90%)"
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_historico(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            picks_total = db.select("picks_diarios")
            ganados = sum(1 for p in picks_total if p.get("resultado") == "ganado")
            perdidos = sum(1 for p in picks_total if p.get("resultado") == "perdido")
            total = ganados + perdidos
            ef = (ganados / total * 100) if total > 0 else 0
        except Exception:
            ganados = perdidos = total = 0
            ef = 0

        msg = (
            "📈 *RENDIMIENTO HISTÓRICO*\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Ganados: *{ganados}*\n"
            f"❌ Perdidos: *{perdidos}*\n"
            f"📊 Total: *{total}*\n"
            f"🎯 Efectividad: *{ef:.1f}%*"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_clima(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("❌ Indica equipo. Ej: /clima BAL")
            return
        team = context.args[0].upper()
        fecha = get_today_et().isoformat()
        try:
            juegos = db.select("juegos", filters={"fecha": fecha})
            j = next((g for g in juegos if g.get("equipo_local") == team or g.get("equipo_visitante") == team), None)
        except Exception:
            j = None

        if not j:
            await update.message.reply_text(f"❌ No hay juego de {team} hoy.")
            return

        msg = f"🌤️ *CLIMA — {j.get('estadio', '')}*\n\n"
        msg += f"🌡️ {j.get('clima_temp_c', '?')}°C / {j.get('clima_temp_f', '?')}°F\n"
        msg += f"💧 Humedad: {j.get('clima_humedad', '?')}%\n"
        msg += f"💨 Viento: {j.get('clima_viento_mph', '?')} mph ({j.get('clima_viento_direccion', '?')})\n"
        msg += f"🌧️ Lluvia: {j.get('clima_lluvia_pct', 0)}%"
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_odds(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("❌ Indica equipo. Ej: /odds NYY")
            return
        team = context.args[0].upper()
        fecha = get_today_et().isoformat()
        try:
            juegos = db.select("juegos", filters={"fecha": fecha})
            j = next((g for g in juegos if g.get("equipo_local") == team or g.get("equipo_visitante") == team), None)
        except Exception:
            j = None

        if not j:
            await update.message.reply_text(f"❌ No hay juego de {team} hoy.")
            return

        msg = f"💰 *CUOTAS — {j['equipo_visitante']} @ {j['equipo_local']}*\n\n"
        msg += f"ML Local: {j.get('ml_local', '—')}\n"
        msg += f"ML Visit: {j.get('ml_visitante', '—')}\n"
        msg += f"RL Local: {j.get('rl_local', '—')} ({j.get('rl_local_odds', '—')})\n"
        msg += f"RL Visit: {j.get('rl_visitante', '—')} ({j.get('rl_visitante_odds', '—')})\n"
        msg += f"Total: {j.get('total_runs', '—')}"
        await update.message.reply_text(msg, parse_mode="Markdown")

    # ========================= ENVÍO AUTOMÁTICO (compatibilidad) =========================

    async def enviar_picks_automatico(self, picks: List[Dict], mensaje_extra: str = ""):
        if not picks:
            return
        msg = mensaje_extra + "🎯 *PICKS DEL DÍA*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for p in picks[:10]:
            tipo = p.get("tipo_pick", "").upper()
            msg += f"*{tipo}*\n"
            juegos = p.get("juegos", [])
            if isinstance(juegos, list):
                for j in juegos[:5]:
                    if isinstance(j, dict):
                        eq = j.get("equipo") or j.get("favorito") or "?"
                        msg += f"• {eq}\n"
            msg += "\n"
        try:
            await self.app.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=msg,
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Error enviando: {e}")
