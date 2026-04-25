"""
PicksProMLB - API REST con FastAPI
Endpoints que consume el dashboard de Vercel
"""

from datetime import date, datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from loguru import logger

from app.utils.config import config
from app.utils.database import db


# Inicializar FastAPI
app = FastAPI(
    title="PicksProMLB API",
    description="API del sistema de análisis MLB con sabermetría",
    version="1.0.0",
)

# CORS para permitir requests desde Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, restringir al dominio del dashboard
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Seguridad básica (opcional)
security = HTTPBearer(auto_error=False)


def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Verifica el token de la API (opcional para protección)"""
    # Por ahora dejamos abierto. Se puede activar luego:
    # if credentials and credentials.credentials != config.API_TOKEN:
    #     raise HTTPException(status_code=401, detail="Token inválido")
    return True


# ========== ENDPOINTS ==========

@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "ok",
        "service": "PicksProMLB API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/juegos")
async def get_juegos(
    fecha: Optional[str] = Query(None, description="Fecha YYYY-MM-DD (default: hoy)"),
):
    """Obtiene todos los juegos de una fecha"""
    try:
        if fecha is None:
            fecha = date.today().isoformat()
        
        juegos = db.select("juegos", filters={"fecha": fecha})
        return {
            "fecha": fecha,
            "total": len(juegos),
            "juegos": juegos,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/juegos/{equipo}")
async def get_juego_por_equipo(
    equipo: str,
    fecha: Optional[str] = Query(None),
):
    """Obtiene el juego de un equipo específico en una fecha"""
    try:
        if fecha is None:
            fecha = date.today().isoformat()
        
        juegos = db.select("juegos", filters={"fecha": fecha})
        juego = next(
            (j for j in juegos if j["equipo_local"] == equipo.upper() or j["equipo_visitante"] == equipo.upper()),
            None
        )
        
        if not juego:
            raise HTTPException(status_code=404, detail=f"No hay juego de {equipo} en {fecha}")
        
        # Agregar análisis si existe
        local = juego["equipo_local"]
        visit = juego["equipo_visitante"]
        analisis = db.select("filtros_aplicados", filters={"fecha": fecha, "equipo_favorecido": local}) or \
                   db.select("filtros_aplicados", filters={"fecha": fecha, "equipo_favorecido": visit})
        
        # Stats de equipos
        stats_local = db.select("equipos_diario", filters={"fecha": fecha, "equipo": local})
        stats_visit = db.select("equipos_diario", filters={"fecha": fecha, "equipo": visit})
        
        return {
            "juego": juego,
            "analisis": analisis[0] if analisis else None,
            "stats_local": stats_local[0] if stats_local else None,
            "stats_visitante": stats_visit[0] if stats_visit else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/picks")
async def get_picks(
    fecha: Optional[str] = Query(None, description="Fecha YYYY-MM-DD"),
):
    """Obtiene los picks recomendados de una fecha"""
    try:
        if fecha is None:
            fecha = date.today().isoformat()
        
        picks = db.select("picks_diarios", filters={"fecha": fecha})
        return {
            "fecha": fecha,
            "total": len(picks),
            "picks": picks,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/filtros")
async def get_filtros_aplicados(
    fecha: Optional[str] = Query(None),
):
    """Obtiene los filtros aplicados a cada juego"""
    try:
        if fecha is None:
            fecha = date.today().isoformat()
        
        filtros = db.select("filtros_aplicados", filters={"fecha": fecha})
        # Ordenar por filtros pasados descendente
        filtros.sort(key=lambda x: x.get("total_filtros_pasados", 0), reverse=True)
        
        return {
            "fecha": fecha,
            "total": len(filtros),
            "filtros": filtros,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/efectividad")
async def get_efectividad():
    """Obtiene la efectividad histórica de cada filtro"""
    try:
        efectividad = db.select("efectividad_filtros")
        return {"filtros": efectividad}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/rendimiento")
async def get_rendimiento(
    dias: int = Query(7, description="Últimos N días"),
):
    """Estadísticas de rendimiento global"""
    try:
        desde = (date.today() - timedelta(days=dias)).isoformat()
        
        client = db.get_client()
        response = client.table("filtros_aplicados") \
            .select("*") \
            .gte("fecha", desde) \
            .not_.is_("resultado_pick", "null") \
            .execute()
        
        data = response.data
        ganados = sum(1 for p in data if p.get("resultado_pick") is True)
        perdidos = sum(1 for p in data if p.get("resultado_pick") is False)
        total = ganados + perdidos
        efectividad = (ganados / total * 100) if total > 0 else 0
        
        # Por nivel de confianza
        por_nivel = {}
        for p in data:
            nivel = p.get("nivel_confianza", "desconocido")
            if nivel not in por_nivel:
                por_nivel[nivel] = {"ganados": 0, "perdidos": 0, "total": 0}
            por_nivel[nivel]["total"] += 1
            if p.get("resultado_pick"):
                por_nivel[nivel]["ganados"] += 1
            else:
                por_nivel[nivel]["perdidos"] += 1
        
        return {
            "periodo_dias": dias,
            "total_picks": total,
            "ganados": ganados,
            "perdidos": perdidos,
            "efectividad": round(efectividad, 2),
            "por_nivel": por_nivel,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/historico")
async def get_historico(
    desde: str = Query(..., description="Fecha inicial YYYY-MM-DD"),
    hasta: Optional[str] = Query(None, description="Fecha final YYYY-MM-DD"),
):
    """Obtiene histórico de picks en un rango de fechas"""
    try:
        if hasta is None:
            hasta = date.today().isoformat()
        
        client = db.get_client()
        response = client.table("filtros_aplicados") \
            .select("*") \
            .gte("fecha", desde) \
            .lte("fecha", hasta) \
            .order("fecha", desc=True) \
            .execute()
        
        return {
            "desde": desde,
            "hasta": hasta,
            "total": len(response.data),
            "picks": response.data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/equipos/{equipo}/stats")
async def get_stats_equipo(
    equipo: str,
    fecha: Optional[str] = Query(None),
):
    """Obtiene las stats de un equipo en una fecha específica"""
    try:
        if fecha is None:
            fecha = date.today().isoformat()
        
        stats = db.select("equipos_diario", filters={"fecha": fecha, "equipo": equipo.upper()})
        bullpen = db.select("bullpenes_diario", filters={"fecha": fecha, "equipo": equipo.upper()})
        
        if not stats:
            raise HTTPException(status_code=404, detail=f"No hay stats de {equipo} en {fecha}")
        
        return {
            "equipo": equipo.upper(),
            "fecha": fecha,
            "stats": stats[0],
            "bullpen": bullpen[0] if bullpen else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/calendario")
async def get_calendario(
    desde: Optional[str] = Query(None),
    hasta: Optional[str] = Query(None),
):
    """Obtiene el calendario de juegos en un rango"""
    try:
        if desde is None:
            desde = date.today().isoformat()
        if hasta is None:
            hasta = (date.today() + timedelta(days=7)).isoformat()
        
        client = db.get_client()
        response = client.table("juegos") \
            .select("*") \
            .gte("fecha", desde) \
            .lte("fecha", hasta) \
            .order("fecha") \
            .order("hora_inicio") \
            .execute()
        
        return {
            "desde": desde,
            "hasta": hasta,
            "juegos": response.data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/log")
async def get_log_ejecuciones(
    dias: int = Query(7),
):
    """Obtiene el log de ejecuciones del sistema"""
    try:
        desde = (date.today() - timedelta(days=dias)).isoformat()
        
        client = db.get_client()
        response = client.table("log_ejecuciones") \
            .select("*") \
            .gte("fecha", desde) \
            .order("created_at", desc=True) \
            .execute()
        
        return {"logs": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== ENDPOINTS DE TRIGGER MANUAL (para testing) ==========

@app.post("/api/trigger/recolectar")
async def trigger_recolectar(authorized: bool = Depends(verify_token)):
    """Dispara recolección manual de datos del día"""
    try:
        from app.collectors.calendar_collector import CalendarCollector
        from app.collectors.team_stats_collector import TeamStatsCollector
        from app.collectors.odds_collector import OddsCollector
        from app.collectors.weather_collector import WeatherCollector
        
        cc = CalendarCollector()
        games = cc.get_games_for_date()
        cc.save_to_db(games)
        
        ts = TeamStatsCollector()
        ts.save_to_db(ts.collect_for_all_teams())
        
        oc = OddsCollector()
        oc.update_db(oc.parse_odds(oc.fetch_odds()))
        
        wc = WeatherCollector()
        wc.update_games_with_weather(games)
        
        return {"status": "ok", "mensaje": f"Recolectados datos de {len(games)} juegos"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/trigger/analizar")
async def trigger_analizar(authorized: bool = Depends(verify_token)):
    """Dispara análisis manual del día"""
    try:
        from app.engine.filter_engine import FilterEngine
        from app.exports.json_builder import ListinJSONBuilder
        from app.agent.gemini_agent import GeminiAgent
        
        FilterEngine().analizar_dia()
        builder = ListinJSONBuilder()
        listin = builder.build()
        
        agent = GeminiAgent()
        analisis = agent.analizar_listin(listin)
        agent.guardar_picks(analisis)
        
        return {"status": "ok", "analisis": analisis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
