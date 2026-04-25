# 🎯 PicksProMLB

Sistema automatizado de análisis MLB con filtros estadísticos avanzados basado en sabermetría (wOBA, wRC+, wRAA, ISO, BABIP, OPS).

## 📊 ¿Qué hace?

1. **Recolecta datos** diariamente de MLB (FanGraphs, MLB Stats API, The Odds API, OpenWeather)
2. **Calcula estadísticas avanzadas** por ventanas de últimos 1, 3, 5, 7 y 10 juegos
3. **Aplica 10 filtros estadísticos** validados con efectividad histórica del 79-94%
4. **Detecta zonas de rebote técnico** y alertas (Coors Field, bullpen explotado, clima adverso)
5. **Genera picks recomendados** con el mejor mercado (ML, Run Line, Team Total, Over/Under)
6. **Te avisa por Telegram** y muestra todo en un dashboard web

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────┐
│   DASHBOARD WEB (Vercel) + BOT TG       │
└─────────────────────────────────────────┘
                  ↑
┌─────────────────────────────────────────┐
│   AGENTE GEMINI (análisis tipster)      │
└─────────────────────────────────────────┘
                  ↑
┌─────────────────────────────────────────┐
│   MOTOR DE FILTROS (F1-F10 + alertas)   │
└─────────────────────────────────────────┘
                  ↑
┌─────────────────────────────────────────┐
│   BASE DE DATOS (Supabase PostgreSQL)   │
└─────────────────────────────────────────┘
                  ↑
┌─────────────────────────────────────────┐
│   RECOLECTOR (pybaseball + APIs)        │
└─────────────────────────────────────────┘
```

## 📁 Estructura del proyecto

```
pickspromlb/
├── app/
│   ├── collectors/      # Scripts que jalan datos de internet
│   ├── engine/          # Motor de filtros y cálculos
│   ├── exports/         # Generación de JSON, Excel, PDF
│   ├── agent/           # Agente Gemini de análisis
│   ├── bot/             # Bot de Telegram
│   ├── dashboard/       # API para el dashboard web
│   └── utils/           # Funciones auxiliares
├── sql/                 # Scripts SQL para Supabase
├── scripts/             # Scripts manuales de utilidad
├── frontend/            # Dashboard React (Vercel)
├── requirements.txt     # Librerías Python
├── .env.example         # Plantilla de variables de entorno
├── .gitignore
└── main.py             # Punto de entrada principal
```

## 🚀 Instalación

Ver `INSTALL.md` para instrucciones paso a paso.

## ⚙️ Variables de entorno necesarias

```
SUPABASE_URL=
SUPABASE_KEY=
ODDS_API_KEY=
OPENWEATHER_API_KEY=
GEMINI_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

## 📅 Los 10 Filtros del sistema

| Filtro | Condición | Efectividad |
|---|---|---|
| F1 | wOBA diff ≥0.040 + wRC+ diff ≥30 | 79% |
| F2 | OPS diff ≥0.150 + wRC+ diff ≥30 | 81% |
| F3 | wRC+ diff ≥30 + wRAA diff >9 | 80% |
| F4 | wOBA diff ≥0.040 + OPS diff ≥0.150 | 82% |
| **F5** | **wRC+ ≥50 + wRAA >12 + wOBA ≥0.070** | **94%** ⭐ |
| F6 | wRC+ ≥30 + wRAA >9 + wOBA ≥0.040 | 83% |
| F7 | wRC+ ≥30 + wRAA >9 + OPS ≥0.150 | 83% |
| F8 | wRC+ ≥30 + wOBA ≥0.040 + OPS ≥0.150 | 82% |
| **F9** | **wRC+ ≥30 + wRAA >9 + BB/K ≥0.2** | **90%** ⭐ |
| F10 | wRC+ ≥40 + wRAA >9 + wOBA ≥0.060 | 82% |

## 🎯 Reglas de decisión

- **8+ filtros pasados** → Directa del día
- **6-7 filtros pasados** → Combinación principal
- **4-5 filtros pasados** → Combinación con colchón (Run Line)
- **0-3 filtros pasados** → No bet

## 📞 Soporte

Sistema privado de uso personal.
