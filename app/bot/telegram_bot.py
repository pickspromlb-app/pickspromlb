"""
PicksProMLB - Bot de Telegram (v2.2 - listín completo + tablas estilo tipster)
Comandos disponibles:
  /start              - Bienvenida
  /ayuda              - Lista de comandos
  /cargar_historico   - PRIMERA VEZ: poblar BD con últimos 20 días (~30 min)
  /estado_cache       - Ver cuánta data hay en caché
  /analizar           - Disparar análisis del día (rápido, lee de caché)
  /listin             - Ver listín del día (RESUMEN COMPLETO)
  /listin_completo    - Ver listín con 4 tablas por juego (estilo tipster)
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
from typing import List, Dict, Optional
import pytz
from loguru import logger
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app.utils.database import db
from app.utils.config import config
from app.utils.time_utils import get_today_et


# Límite de Telegram por mensaje (4096 caracteres)
TELEGRAM_MAX_MSG = 4000


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
        self.app.add_handler(CommandHandler("listin_completo", self.cmd_listin_completo))
        self.app.add_handler(CommandHandler("picks", self.cmd_picks))
        self.app.add_handler(CommandHandler("juegos", self.cmd_juegos))
        self.app.add_handler(CommandHandler("juego", self.cmd_juego))
        self.app.add_handler(CommandHandler("filtros", self.cmd_filtros))
        self.app.add_handler(CommandHandler("historico", self.cmd_historico))
        self.app.add_handler(CommandHandler("clima", self.cmd_clima))
        self.app.add_handler(CommandHandler("odds", self.cmd_odds))
        self.app.add_handler(CommandHandler("rendimiento", self.cmd_historico))

    # ========================= UTILIDADES =========================

    async def _enviar_largo(self, update: Update, msg: str, parse_mode: str = "Markdown"):
        """Envía un mensaje, partiéndolo si es muy largo (>4000 chars)"""
        if len(msg) <= TELEGRAM_MAX_MSG:
            await update.message.reply_text(msg, parse_mode=parse_mode)
            return

        partes = []
        actual = ""
        for bloque in msg.split("\n\n"):
            candidato = (actual + "\n\n" + bloque).strip() if actual else bloque
            if len(candidato) > TELEGRAM_MAX_MSG:
                if actual:
                    partes.append(actual)
                actual = bloque
            else:
                actual = candidato
        if actual:
            partes.append(actual)

        for i, p in enumerate(partes):
            sufijo = f"\n\n_({i+1}/{len(partes)})_" if len(partes) > 1 else ""
            try:
                await update.message.reply_text(p + sufijo, parse_mode=parse_mode)
            except Exception:
                await update.message.reply_text(p + sufijo)

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
            "/listin - Resumen completo del día\n"
            "/listin\\_completo - Listín con tablas (estilo tipster)\n"
            "/picks - Picks recomendados\n"
            "/juegos - Juegos del día\n\n"
            "Escribe /ayuda para ver todos los comandos."
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_ayuda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = (
            "📋 *COMANDOS DISPONIBLES*\n\n"
            "🏗️ *Setup (primera vez)*\n"
            "/cargar\\_historico - Poblar BD (20 días)\n"
            "/estado\\_cache - Ver estado de la caché\n\n"
            "🚀 *Análisis*\n"
            "/analizar - Análisis completo del día\n"
            "/listin - Resumen completo del día\n"
            "/listin AAAA-MM-DD - Listín de fecha pasada\n"
            "/listin\\_completo - Listín con 4 tablas por juego\n"
            "/listin\\_completo TEAM - Solo el juego de un equipo\n"
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

        top = sorted(estado.items(), key=lambda x: -x[1]["total_juegos"])[:5]
        msg += "*Top equipos con más data:*\n"
        for team, data in top:
            msg += f"• {team}: {data['total_juegos']} juegos (último: {data['ultimo_juego'] or '—'})\n"

        if equipos_con_data == 0:
            msg += "\n💡 Usa /cargar_historico para empezar."

        await update.message.reply_text(msg, parse_mode="Markdown")

    # ========================= /analizar =========================

    async def cmd_analizar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        try:
            await self.orchestrator.task_generar_listin_manual()
            await self.app.bot.send_message(
                chat_id=chat_id,
                text="✅ *Análisis completado*\n\nUsa /listin para resumen o /listin\\_completo para todas las tablas.",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Error en análisis: {e}")
            await self.app.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Error en el análisis: {str(e)[:300]}",
            )

    # ========================= /listin (RESUMEN COMPLETO) =========================

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
        msg = self._formatear_listin_resumen(listin, target_date)
        await self._enviar_largo(update, msg)

    def _formatear_listin_resumen(self, listin: Dict, target_date: date) -> str:
        """Formatea el listín con TODAS las directas, combinaciones, RLs y no bets"""
        meta = listin.get("metadata", {})
        picks = listin.get("picks", {})

        msg = f"📋 *LISTÍN MLB — {target_date.strftime('%d/%m/%Y')}*\n"
        msg += f"_{meta.get('total_juegos', 0)} juegos analizados_\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

        # ===== 1) TODAS LAS DIRECTAS DEL DÍA =====
        todas_directas = picks.get("todas_las_directas") or []
        if not todas_directas and picks.get("directa_del_dia"):
            todas_directas = [picks["directa_del_dia"]]

        if todas_directas:
            titulo = "🎯 *DIRECTA DEL DÍA*" if len(todas_directas) == 1 else f"🎯 *DIRECTAS DEL DÍA ({len(todas_directas)})*"
            msg += f"{titulo}\n"
            for d in todas_directas:
                pick_str = d.get("pick") or f"{d.get('favorito')} a ganar"
                hora = d.get("hora_et", "TBD")
                matchup = d.get("matchup", "?")
                filtros = d.get("filtros_pasados", 0)
                msg += f"➡️ *{pick_str}*\n"
                msg += f"   📍 {matchup} · {hora} · ✅ {filtros}/10\n"
                if d.get("alertas"):
                    for a in d["alertas"][:2]:
                        msg += f"   {a}\n"
            msg += "\n"

        # ===== 2) COMBINACIÓN PRINCIPAL =====
        combo_principal = picks.get("combinacion_principal") or []
        if combo_principal:
            msg += f"💎 *COMBINACIÓN PRINCIPAL ({len(combo_principal)})*\n"
            for c in combo_principal:
                pick_str = c.get("pick") or f"{c.get('favorito')} ML"
                hora = c.get("hora_et", "TBD")
                matchup = c.get("matchup", "?")
                filtros = c.get("filtros_pasados", 0)
                msg += f"• *{pick_str}*\n"
                msg += f"  └ {matchup} · {hora} · {filtros}/10\n"
            msg += "\n"

        # ===== 3) COMBINACIÓN SECUNDARIA =====
        combo_sec = picks.get("combinacion_secundaria") or []
        if combo_sec:
            msg += f"💠 *COMBINACIÓN SECUNDARIA ({len(combo_sec)})*\n"
            for c in combo_sec:
                pick_str = c.get("pick") or f"{c.get('favorito')}"
                hora = c.get("hora_et", "TBD")
                matchup = c.get("matchup", "?")
                filtros = c.get("filtros_pasados", 0)
                msg += f"• *{pick_str}*\n"
                msg += f"  └ {matchup} · {hora} · {filtros}/10\n"
            msg += "\n"

        # ===== 4) RUN LINES ALTERNATIVAS =====
        run_lines = picks.get("run_lines_alternativas") or []
        if run_lines:
            ya_listados = set()
            for c in combo_principal + combo_sec:
                ya_listados.add((c.get("matchup"), c.get("pick")))
            run_lines_unicas = [
                r for r in run_lines
                if (r.get("matchup"), r.get("pick")) not in ya_listados
            ]
            if run_lines_unicas:
                msg += f"🛡️ *RUN LINES ALTERNATIVAS ({len(run_lines_unicas)})*\n"
                for r in run_lines_unicas:
                    pick_str = r.get("pick") or f"{r.get('favorito')} RL +1.5"
                    hora = r.get("hora_et", "TBD")
                    matchup = r.get("matchup", "?")
                    filtros = r.get("filtros_pasados", 0)
                    msg += f"• *{pick_str}*\n"
                    msg += f"  └ {matchup} · {hora} · {filtros}/10\n"
                msg += "\n"

        # ===== 5) NO BETS (resumen compacto) =====
        no_bets = picks.get("no_bets") or []
        if no_bets:
            msg += f"🚫 *NO BETS ({len(no_bets)})*\n"
            matchups_no_bet = [nb.get("matchup", "?") for nb in no_bets]
            msg += "_" + " · ".join(matchups_no_bet) + "_\n\n"

        if not (todas_directas or combo_principal or combo_sec or run_lines or no_bets):
            msg += "_No hay picks generados todavía. Usa /analizar._\n\n"

        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "📖 Detalle de juego: /juego TEAM\n"
        msg += "📑 Tablas completas: /listin\\_completo\n"
        msg += f"🌐 Web: https://pickspromlb.vercel.app/listin/{target_date.isoformat()}"
        return msg

    # ========================= /listin_completo (TABLAS ESTILO TIPSTER) =========================

    async def cmd_listin_completo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra el listín con las 4 tablas por juego, estilo tipster venezolano.
        Uso:
          /listin_completo            → todos los juegos (en mensajes separados)
          /listin_completo TEAM       → solo el juego de ese equipo
        """
        target_date = get_today_et()
        team_filter: Optional[str] = None
        if context.args:
            team_filter = context.args[0].upper()

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
        juegos = listin.get("juegos", []) or []

        if team_filter:
            juegos = [
                j for j in juegos
                if j.get("equipo_local") == team_filter or j.get("equipo_visitante") == team_filter
            ]
            if not juegos:
                await update.message.reply_text(
                    f"❌ No hay juego de {team_filter} en el listín de hoy."
                )
                return

        if not juegos:
            await update.message.reply_text("⚠️ El listín está vacío.")
            return

        # Cabecera
        encabezado = (
            f"📋 *LISTÍN COMPLETO — {target_date.strftime('%d/%m/%Y')}*\n"
            f"_{len(juegos)} juego(s) con tablas detalladas_\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
        )
        try:
            await update.message.reply_text(encabezado, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(encabezado)

        # Un mensaje por juego (las tablas son largas)
        for i, juego in enumerate(juegos, start=1):
            msg = self._formatear_juego_completo(juego, i, len(juegos))
            try:
                await update.message.reply_text(msg, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(msg)
            await asyncio.sleep(0.3)

    def _formatear_juego_completo(self, juego: Dict, idx: int, total: int) -> str:
        """Formatea un juego con sus 4 tablas estilo tipster"""
        local = juego.get("equipo_local", "?")
        visit = juego.get("equipo_visitante", "?")
        matchup = juego.get("matchup", f"{visit} @ {local}")
        hora = juego.get("hora_et", "TBD")
        estadio = juego.get("estadio", "TBD")
        pitcher_v = juego.get("pitcher_visitante", "TBD")
        pitcher_l = juego.get("pitcher_local", "TBD")

        analisis = juego.get("analisis", {}) or {}
        pick = analisis.get("pick", "—")
        favorito = analisis.get("favorito", "—")
        confianza = (analisis.get("confianza") or "—").upper()
        filtros_lista = analisis.get("filtros_pasados") or []
        if isinstance(filtros_lista, int):
            total_filtros = filtros_lista
            filtros_str = "—"
        else:
            total_filtros = analisis.get("total_filtros", len(filtros_lista))
            filtros_str = ", ".join(filtros_lista) if filtros_lista else "ninguno"

        msg = f"━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"⚾ *JUEGO {idx}/{total}: {matchup}*\n"
        msg += f"📍 {estadio} · ⏰ {hora}\n"
        msg += f"🎯 {pitcher_v} vs {pitcher_l}\n\n"

        # Pick destacado
        msg += f"🎲 *PICK:* {pick}\n"
        msg += f"   Favorito: *{favorito}* · Confianza: *{confianza}*\n"
        msg += f"   Filtros: *{total_filtros}/10* ({filtros_str})\n\n"

        # ===== TABLA 1: TEMPORADA =====
        tabla_temp = juego.get("tabla_temporada", {})
        if tabla_temp.get("filas"):
            msg += f"📊 *{tabla_temp.get('titulo', 'TEMPORADA')}*\n"
            msg += "```\n"
            msg += f"{'Equipo':<6}{'J':>4}{'C':>5}{'AVG':>7}{'OBP':>7}{'OPS':>7}\n"
            for fila in tabla_temp["filas"]:
                msg += f"{fila.get('equipo','?'):<6}"
                msg += f"{fila.get('juegos',0):>4}"
                msg += f"{fila.get('carreras',0):>5}"
                msg += f"{fila.get('avg',0):>7.3f}"
                msg += f"{fila.get('obp',0):>7.3f}"
                msg += f"{fila.get('ops',0):>7.3f}"
                msg += "\n"
            msg += "```\n"

        # ===== TABLA 2: ESTADÍSTICAS AVANZADAS =====
        tabla_av = juego.get("tabla_avanzadas", {})
        if tabla_av.get("filas"):
            msg += f"\n🔬 *{tabla_av.get('titulo', 'AVANZADAS')}*\n"
            msg += "```\n"
            msg += f"{'Eq':<5}{'wOBA':>7}{'wRC+':>6}{'wRAA':>7}{'BB/K':>6}{'BABIP':>7}\n"
            for fila in tabla_av["filas"]:
                msg += f"{fila.get('equipo','?'):<5}"
                msg += f"{fila.get('woba',0):>7.3f}"
                msg += f"{fila.get('wrc_plus',0):>6}"
                msg += f"{fila.get('wraa',0):>7.2f}"
                msg += f"{fila.get('bbk',0):>6.2f}"
                msg += f"{fila.get('babip',0):>7.3f}"
                msg += "\n"
            msg += "```\n"

        # ===== TABLA 3: CÓMO LLEGAN (últimos días) =====
        tabla_ult = juego.get("tabla_ultimos_dias", {})
        if tabla_ult.get("filas"):
            msg += f"\n📈 *{tabla_ult.get('titulo', 'ÚLTIMOS DÍAS')}*\n"
            msg += "```\n"
            msg += f"{'Eq':<5}{'Vent':>5}{'OPS':>7}{'wOBA':>7}{'wRC+':>6}{'wRAA':>7}\n"
            for fila in tabla_ult["filas"]:
                msg += f"{fila.get('equipo','?'):<5}"
                msg += f"{fila.get('ventana','?'):>5}"
                msg += f"{fila.get('ops',0):>7.3f}"
                msg += f"{fila.get('woba',0):>7.3f}"
                msg += f"{fila.get('wrc_plus',0):>6}"
                msg += f"{fila.get('wraa',0):>7.2f}"
                msg += "\n"
            msg += "```\n"

        # ===== TABLA 4: BULLPENES =====
        tabla_bp = juego.get("tabla_bullpenes", {})
        if tabla_bp.get("filas"):
            msg += f"\n🧤 *{tabla_bp.get('titulo', 'BULLPENES')}*\n"
            msg += "```\n"
            msg += f"{'Eq':<5}{'IP':>6}{'ERA':>7}{'WHIP':>7}{'K/9':>6}{'BB/9':>6}\n"
            for fila in tabla_bp["filas"]:
                msg += f"{fila.get('equipo','?'):<5}"
                msg += f"{fila.get('ip',0):>6.1f}"
                msg += f"{fila.get('era',0):>7.2f}"
                msg += f"{fila.get('whip',0):>7.2f}"
                msg += f"{fila.get('k_9',0):>6.1f}"
                msg += f"{fila.get('bb_9',0):>6.1f}"
                msg += "\n"
            msg += "```\n"

        # ===== ALERTAS =====
        alertas = analisis.get("alertas") or []
        if alertas:
            msg += "\n⚠️ *Alertas:*\n"
            for a in alertas[:5]:
                msg += f"• {a}\n"

        # ===== CLIMA =====
        clima = juego.get("clima", {})
        if clima.get("temp_c") is not None:
            msg += f"\n🌤️ Clima: {clima.get('temp_c')}°C / {clima.get('temp_f')}°F · "
            msg += f"💧 {clima.get('humedad')}% · "
            msg += f"🌧️ {clima.get('lluvia_pct')}% · "
            msg += f"💨 {clima.get('viento_mph')}mph"

        # ===== ODDS =====
        mercado = juego.get("mercado", {}) or {}
        if any(v is not None for v in mercado.values()):
            msg += "\n💰 *Cuotas:* "
            partes = []
            if mercado.get("ml_local") is not None:
                partes.append(f"ML {local} {mercado['ml_local']}")
            if mercado.get("ml_visitante") is not None:
                partes.append(f"ML {visit} {mercado['ml_visitante']}")
            if mercado.get("total") is not None:
                partes.append(f"Total {mercado['total']}")
            msg += " · ".join(partes)

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

        await self._enviar_largo(update, msg)

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
            equipo_consultar = a.get('equipo_favorecido') or team
            msg += f"\n📑 Tablas: /listin\\_completo {equipo_consultar}"
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
