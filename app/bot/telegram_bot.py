"""
PicksProMLB - Bot de Telegram
Soporta comandos manuales (/picks, /historico, etc.) y envío automático de picks
"""

import asyncio
from datetime import date, datetime, timedelta
from typing import Optional
from loguru import logger

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from app.utils.config import config
from app.utils.database import db


class PicksProBot:
    """Bot de Telegram para PicksProMLB"""
    
    def __init__(self):
        if not config.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN no configurada")
        
        self.token = config.TELEGRAM_BOT_TOKEN
        self.chat_id = config.TELEGRAM_CHAT_ID
        self.app = Application.builder().token(self.token).build()
        self._registrar_handlers()
    
    def _registrar_handlers(self):
        """Registra todos los comandos del bot"""
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("ayuda", self.cmd_ayuda))
        self.app.add_handler(CommandHandler("help", self.cmd_ayuda))
        self.app.add_handler(CommandHandler("picks", self.cmd_picks))
        self.app.add_handler(CommandHandler("juegos", self.cmd_juegos))
        self.app.add_handler(CommandHandler("juego", self.cmd_juego))
        self.app.add_handler(CommandHandler("filtros", self.cmd_filtros))
        self.app.add_handler(CommandHandler("historico", self.cmd_historico))
        self.app.add_handler(CommandHandler("clima", self.cmd_clima))
        self.app.add_handler(CommandHandler("odds", self.cmd_odds))
        self.app.add_handler(CommandHandler("rendimiento", self.cmd_rendimiento))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
    
    # ========== COMANDOS ==========
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start - bienvenida"""
        chat_id = update.effective_chat.id
        nombre = update.effective_user.first_name
        
        mensaje = f"""
🎯 *¡Bienvenido a PicksProMLB, {nombre}!*

Sistema automatizado de análisis MLB con filtros estadísticos avanzados.

*Tu Chat ID es:* `{chat_id}`
👆 Guárdalo en tu archivo de configuración como `TELEGRAM_CHAT_ID`

📋 *Comandos disponibles:*
/picks - Picks recomendados del día
/juegos - Lista de juegos del día con filtros
/juego [equipo] - Detalle de un juego específico
/filtros - Estado de los 10 filtros
/historico - Mi rendimiento (últimos días)
/clima [estadio] - Clima del juego
/odds [equipo] - Cuotas actualizadas
/rendimiento - Estadísticas globales
/ayuda - Esta ayuda

⚡ *Recibirás picks automáticamente* 4 horas antes del primer juego del día.
"""
        await update.message.reply_text(mensaje, parse_mode="Markdown")
    
    async def cmd_ayuda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /ayuda"""
        await self.cmd_start(update, context)
    
    async def cmd_picks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /picks - muestra picks del día"""
        try:
            fecha_str = date.today().isoformat()
            picks = db.select("picks_diarios", filters={"fecha": fecha_str})
            
            if not picks:
                await update.message.reply_text(
                    "⚠️ No hay picks generados aún para hoy.\n"
                    "El sistema genera picks 4 horas antes del primer juego."
                )
                return
            
            mensaje = self._formatear_picks(picks)
            await update.message.reply_text(mensaje, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error en /picks: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def cmd_juegos(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /juegos - lista juegos del día con filtros"""
        try:
            fecha_str = date.today().isoformat()
            
            # Obtener juegos
            juegos = db.select("juegos", filters={"fecha": fecha_str})
            if not juegos:
                await update.message.reply_text("⚠️ No hay juegos programados para hoy.")
                return
            
            # Obtener filtros
            filtros = db.select("filtros_aplicados", filters={"fecha": fecha_str})
            filtros_map = {(f["equipo_favorecido"], f["equipo_rival"]): f for f in filtros}
            
            mensaje = f"⚾ *JUEGOS DEL DÍA - {date.today().strftime('%d/%m/%Y')}*\n\n"
            
            for j in juegos:
                local = j["equipo_local"]
                visit = j["equipo_visitante"]
                f = filtros_map.get((local, visit)) or filtros_map.get((visit, local))
                
                total = f["total_filtros_pasados"] if f else 0
                fav = f["equipo_favorecido"] if f else "—"
                
                emoji = self._get_emoji_filtros(total)
                hora = self._formatear_hora(j.get("hora_inicio"))
                
                mensaje += f"{emoji} *{visit} @ {local}* — {hora}\n"
                if f:
                    mensaje += f"   Favorito: *{fav}* ({total}/10 filtros)\n"
                mensaje += "\n"
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error en /juegos: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def cmd_juego(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /juego [equipo] - detalle de un juego"""
        if not context.args:
            await update.message.reply_text(
                "ℹ️ Uso: `/juego <abreviacion>`\nEjemplo: `/juego MIA`",
                parse_mode="Markdown"
            )
            return
        
        equipo = context.args[0].upper()
        try:
            fecha_str = date.today().isoformat()
            juegos = db.select("juegos", filters={"fecha": fecha_str})
            
            juego = next((j for j in juegos if j["equipo_local"] == equipo or j["equipo_visitante"] == equipo), None)
            if not juego:
                await update.message.reply_text(f"⚠️ No encontré juego de {equipo} para hoy.")
                return
            
            mensaje = self._formatear_detalle_juego(juego)
            await update.message.reply_text(mensaje, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def cmd_filtros(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /filtros - efectividad de los 10 filtros"""
        try:
            efectividad = db.select("efectividad_filtros")
            
            mensaje = "📊 *EFECTIVIDAD DE FILTROS*\n\n"
            for f in sorted(efectividad, key=lambda x: x.get("filtro", "")):
                emoji = "⭐" if f["porcentaje_efectividad"] >= 90 else "✅" if f["porcentaje_efectividad"] >= 80 else "📊"
                mensaje += f"{emoji} *{f['filtro']}* — {f['porcentaje_efectividad']:.1f}%\n"
                mensaje += f"   {f['descripcion']}\n\n"
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def cmd_historico(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /historico - rendimiento últimos 7 días"""
        try:
            hace_7_dias = (date.today() - timedelta(days=7)).isoformat()
            
            # Obtener picks recientes (esto se puede mejorar con una query SQL)
            client = db.get_client()
            response = client.table("filtros_aplicados") \
                .select("*") \
                .gte("fecha", hace_7_dias) \
                .not_.is_("resultado_pick", "null") \
                .execute()
            
            data = response.data
            if not data:
                await update.message.reply_text("📊 No hay datos históricos aún.")
                return
            
            ganados = sum(1 for p in data if p.get("resultado_pick") is True)
            perdidos = sum(1 for p in data if p.get("resultado_pick") is False)
            total = ganados + perdidos
            efectividad = (ganados / total * 100) if total > 0 else 0
            
            mensaje = f"""
📊 *RENDIMIENTO ÚLTIMOS 7 DÍAS*

🎯 Total picks: {total}
✅ Ganados: {ganados}
❌ Perdidos: {perdidos}
📈 Efectividad: *{efectividad:.1f}%*
"""
            await update.message.reply_text(mensaje, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def cmd_clima(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /clima - clima de los estadios del día"""
        try:
            fecha_str = date.today().isoformat()
            juegos = db.select("juegos", filters={"fecha": fecha_str})
            
            if not juegos:
                await update.message.reply_text("⚠️ No hay juegos para hoy.")
                return
            
            mensaje = f"🌤️ *CLIMA DEL DÍA - {date.today().strftime('%d/%m/%Y')}*\n\n"
            for j in juegos:
                if j.get("clima_temp_c") is None:
                    continue
                
                emoji = self._get_emoji_clima(j)
                mensaje += f"{emoji} *{j['estadio']}*\n"
                mensaje += f"   {j['equipo_visitante']} @ {j['equipo_local']}\n"
                mensaje += f"   🌡️ {j['clima_temp_c']}°C / {j['clima_temp_f']}°F\n"
                mensaje += f"   💧 Humedad: {j['clima_humedad']}%\n"
                mensaje += f"   💨 Viento: {j['clima_viento_mph']} mph {j['clima_viento_direccion']}\n"
                if j.get("clima_lluvia_pct", 0) > 0:
                    mensaje += f"   🌧️ Lluvia: {j['clima_lluvia_pct']}%\n"
                mensaje += "\n"
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def cmd_odds(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /odds - cuotas del día"""
        try:
            fecha_str = date.today().isoformat()
            juegos = db.select("juegos", filters={"fecha": fecha_str})
            
            mensaje = f"💰 *CUOTAS DEL DÍA*\n\n"
            for j in juegos:
                ml_l = j.get("ml_local")
                ml_v = j.get("ml_visitante")
                total = j.get("total_runs")
                
                if ml_l is None:
                    continue
                
                mensaje += f"⚾ *{j['equipo_visitante']} @ {j['equipo_local']}*\n"
                mensaje += f"   ML: {j['equipo_visitante']} ({ml_v:+}) | {j['equipo_local']} ({ml_l:+})\n"
                if total:
                    mensaje += f"   Total: {total}\n"
                mensaje += "\n"
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def cmd_rendimiento(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /rendimiento - rendimiento global del sistema"""
        try:
            client = db.get_client()
            response = client.table("filtros_aplicados") \
                .select("*") \
                .not_.is_("resultado_pick", "null") \
                .execute()
            
            data = response.data
            if not data:
                await update.message.reply_text("📊 No hay datos suficientes aún.")
                return
            
            # Stats globales
            ganados = sum(1 for p in data if p.get("resultado_pick") is True)
            perdidos = sum(1 for p in data if p.get("resultado_pick") is False)
            total = ganados + perdidos
            efectividad = (ganados / total * 100) if total > 0 else 0
            
            # Por nivel de confianza
            por_nivel = {}
            for p in data:
                nivel = p.get("nivel_confianza", "desconocido")
                if nivel not in por_nivel:
                    por_nivel[nivel] = {"g": 0, "p": 0}
                if p.get("resultado_pick"):
                    por_nivel[nivel]["g"] += 1
                else:
                    por_nivel[nivel]["p"] += 1
            
            mensaje = f"""
📈 *RENDIMIENTO GLOBAL*

🎯 Total: {total} picks
✅ Ganados: {ganados}
❌ Perdidos: {perdidos}
📊 Efectividad: *{efectividad:.1f}%*

*Por nivel de confianza:*
"""
            for nivel, stats in por_nivel.items():
                t = stats["g"] + stats["p"]
                ef = (stats["g"] / t * 100) if t > 0 else 0
                mensaje += f"• {nivel}: {stats['g']}/{t} ({ef:.1f}%)\n"
            
            await update.message.reply_text(mensaje, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    # ========== HELPERS ==========
    
    def _get_emoji_filtros(self, total: int) -> str:
        if total >= 8:
            return "🟢"
        elif total >= 6:
            return "🟡"
        elif total >= 4:
            return "🟠"
        else:
            return "⚪"
    
    def _get_emoji_clima(self, juego: dict) -> str:
        temp = juego.get("clima_temp_c", 20)
        lluvia = juego.get("clima_lluvia_pct", 0)
        if lluvia > 30:
            return "🌧️"
        elif temp < 10:
            return "❄️"
        elif temp > 27:
            return "☀️"
        else:
            return "🌤️"
    
    def _formatear_hora(self, hora_str: str) -> str:
        if not hora_str:
            return "TBD"
        try:
            dt = datetime.fromisoformat(hora_str.replace("Z", "+00:00"))
            return dt.strftime("%I:%M %p ET").lstrip("0")
        except:
            return hora_str
    
    def _formatear_picks(self, picks: list) -> str:
        mensaje = f"🎯 *PICKS DEL DÍA - {date.today().strftime('%d/%m/%Y')}*\n\n"
        
        for pick in picks:
            tipo = pick["tipo_pick"].upper()
            mensaje += f"━━━━━━━━━━━━━━━━━━\n"
            mensaje += f"📌 *{tipo.replace('_', ' ')}*\n\n"
            
            juegos = pick.get("juegos", [])
            for j in juegos:
                if isinstance(j, dict):
                    mensaje += f"• {j.get('juego', '?')}\n"
                    mensaje += f"  Pick: *{j.get('pick', '?')}*\n"
                    if j.get("cuota"):
                        mensaje += f"  Cuota: {j['cuota']}\n"
                    if j.get("filtros"):
                        mensaje += f"  Filtros: {j['filtros']}/10\n"
                    if j.get("razon"):
                        mensaje += f"  💡 {j['razon']}\n"
                    mensaje += "\n"
            
            if pick.get("cuota_total"):
                mensaje += f"💰 *Cuota total: {pick['cuota_total']}*\n"
            mensaje += "\n"
        
        return mensaje
    
    def _formatear_detalle_juego(self, juego: dict) -> str:
        mensaje = f"⚾ *{juego['equipo_visitante']} @ {juego['equipo_local']}*\n"
        mensaje += f"📅 {juego['fecha']}\n"
        mensaje += f"⏰ {self._formatear_hora(juego.get('hora_inicio'))}\n"
        mensaje += f"🏟️ {juego.get('estadio', 'TBD')}\n\n"
        
        if juego.get("pitcher_local"):
            mensaje += f"⚾ Pitchers:\n"
            mensaje += f"  {juego['equipo_local']}: {juego['pitcher_local']}\n"
            mensaje += f"  {juego['equipo_visitante']}: {juego.get('pitcher_visitante', 'TBD')}\n\n"
        
        if juego.get("ml_local"):
            mensaje += f"💰 Cuotas:\n"
            mensaje += f"  ML: {juego['equipo_local']} ({juego['ml_local']:+}) | {juego['equipo_visitante']} ({juego['ml_visitante']:+})\n"
            if juego.get("total_runs"):
                mensaje += f"  Total: {juego['total_runs']}\n\n"
        
        if juego.get("clima_temp_c") is not None:
            mensaje += f"🌤️ Clima: {juego['clima_temp_c']}°C, {juego.get('clima_humedad', 0)}% humedad\n"
        
        return mensaje
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja botones inline"""
        query = update.callback_query
        await query.answer()
        # Implementar lógica de botones aquí
    
    # ========== ENVÍO AUTOMÁTICO ==========
    
    async def enviar_picks_automatico(self, picks: list, mensaje_extra: str = ""):
        """Envía picks automáticamente al chat configurado"""
        if not self.chat_id:
            logger.warning("⚠️ TELEGRAM_CHAT_ID no configurado, no puedo enviar automático")
            return
        
        try:
            mensaje = mensaje_extra + "\n" + self._formatear_picks(picks)
            await self.app.bot.send_message(
                chat_id=self.chat_id,
                text=mensaje,
                parse_mode="Markdown"
            )
            logger.info(f"📤 Picks enviados automáticamente al chat {self.chat_id}")
        except Exception as e:
            logger.error(f"❌ Error enviando picks automáticos: {e}")
    
    def run(self):
        """Inicia el bot en modo polling (escucha comandos)"""
        logger.info("🤖 Bot iniciado, escuchando comandos...")
        self.app.run_polling()


if __name__ == "__main__":
    bot = PicksProBot()
    bot.run()
