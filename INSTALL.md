# 🚀 GUÍA DE INSTALACIÓN - PicksProMLB

Esta guía te lleva paso a paso desde tener las cuentas creadas hasta tener el sistema funcionando.

---

## 📋 Pre-requisitos (ya completados)

Si llegaste aquí, asumimos que ya tienes:

- ✅ Cuenta Gmail (`pickspromlb@gmail.com`)
- ✅ Cuenta GitHub (`pickspromlb-app`)
- ✅ Proyecto Supabase (`pickspromlb-db`)
- ✅ Cuenta Railway (con $5 de trial)
- ✅ Cuenta Vercel (Hobby)
- ✅ Bot de Telegram (`@PicksProMLB_bot`)
- ✅ API Keys: The Odds API, OpenWeather, Gemini

---

## 📦 FASE 1: Subir el código a GitHub

### Paso 1.1: Descargar el código

El código está organizado en `/home/claude/pickspromlb/`. Lo descargarás como un archivo ZIP.

### Paso 1.2: Crear repositorio en GitHub (si no existe)

1. Ve a https://github.com/new
2. **Repository name:** `pickspromlb`
3. **Description:** `Sistema MLB con sabermetría avanzada`
4. ✅ **Private**
5. ❌ NO marques "Initialize this repository"
6. Click **"Create repository"**

### Paso 1.3: Subir el código

**Opción A — Con interfaz web (más fácil):**

1. En GitHub, en tu repo nuevo, click **"uploading an existing file"**
2. Arrastra TODOS los archivos del proyecto descomprimido
3. Commit message: `Initial commit - PicksProMLB`
4. Click **"Commit changes"**

**Opción B — Con Git desde tu computadora:**

```bash
cd /ruta/al/proyecto/pickspromlb
git init
git add .
git commit -m "Initial commit - PicksProMLB"
git branch -M main
git remote add origin https://github.com/pickspromlb-app/pickspromlb.git
git push -u origin main
```

---

## 🗄️ FASE 2: Configurar la Base de Datos

### Paso 2.1: Abrir SQL Editor en Supabase

1. Entra a https://supabase.com/dashboard
2. Click en tu proyecto **pickspromlb-db**
3. En el menú lateral, click en el icono **SQL Editor** (icono de terminal `>_`)
4. Click en **"New query"**

### Paso 2.2: Ejecutar el schema

1. Abre el archivo `sql/01_schema.sql` desde tu computadora
2. Copia TODO el contenido
3. Pégalo en el SQL Editor de Supabase
4. Click en **"Run"** (o Ctrl+Enter)
5. Espera el mensaje: `✅ Schema de PicksProMLB creado exitosamente`

### Paso 2.3: Verificar las tablas

1. En el menú lateral, click en **"Table Editor"** (icono de tabla)
2. Deberías ver estas 8 tablas:
   - `equipos_diario`
   - `bullpenes_diario`
   - `juegos`
   - `filtros_aplicados`
   - `historico_metricas`
   - `efectividad_filtros` (con 10 filtros precargados)
   - `picks_diarios`
   - `log_ejecuciones`

---

## 🤖 FASE 3: Obtener tu Telegram Chat ID

### Paso 3.1: Abre tu bot

1. Abre Telegram (web o móvil)
2. Busca: **@PicksProMLB_bot**
3. Click **START** o escribe `/start`

### Paso 3.2: Recibe tu Chat ID

El bot te responderá automáticamente con tu **Chat ID** (un número como `123456789`).

⚠️ **Guarda este número** - lo necesitarás para Railway.

---

## 🚂 FASE 4: Deploy del Backend a Railway

### Paso 4.1: Conectar Railway a GitHub

1. Entra a https://railway.com/dashboard
2. Click en **"+ New"** (arriba a la derecha)
3. Selecciona **"Deploy from GitHub repo"**
4. Si es la primera vez, autoriza Railway para acceder a tus repos
5. Selecciona el repo **`pickspromlb-app/pickspromlb`**
6. Click **"Deploy Now"**

Railway empezará a buildear automáticamente. Esto tomará 3-5 minutos.

### Paso 4.2: Configurar variables de entorno

Mientras buildea, en el dashboard de tu proyecto Railway:

1. Click en el servicio que se creó
2. Click en la pestaña **"Variables"**
3. Click **"+ New Variable"** y agrega UNA POR UNA estas variables:

```
SUPABASE_URL=https://xbgoojewccjuhzvxpxqg.supabase.co
SUPABASE_KEY=[tu secret key de Supabase, empieza con sb_secret_]
SUPABASE_ANON_KEY=[tu publishable key de Supabase, empieza con sb_publishable_]
ODDS_API_KEY=[tu key de The Odds API]
OPENWEATHER_API_KEY=[tu key de OpenWeather]
GEMINI_API_KEY=[tu key de Gemini]
GEMINI_MODEL=gemini-2.0-flash-exp
TELEGRAM_BOT_TOKEN=[tu token de @PicksProMLB_bot]
TELEGRAM_CHAT_ID=[tu chat_id de Telegram]
TIMEZONE=America/New_York
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### Paso 4.3: Re-deploy con variables

1. Click en pestaña **"Deployments"**
2. Click en los **3 puntos** del último deploy
3. Click **"Redeploy"**

Railway re-buildeará con las variables nuevas.

### Paso 4.4: Generar URL pública

1. En tu servicio Railway, click pestaña **"Settings"**
2. Scroll a **"Networking"**
3. Click **"Generate Domain"**
4. Te dará una URL como: `https://pickspromlb-production.up.railway.app`

⚠️ **Guarda esta URL** - es tu API. La usarás en Vercel.

### Paso 4.5: Verificar que funciona

Abre en tu navegador:

```
https://[tu-url-railway].up.railway.app/
```

Deberías ver:
```json
{
  "status": "ok",
  "service": "PicksProMLB API",
  "version": "1.0.0"
}
```

✅ Si ves esto, **el backend funciona**.

---

## 🌐 FASE 5: Deploy del Frontend a Vercel

### Paso 5.1: Importar repo a Vercel

1. Entra a https://vercel.com/new
2. Click **"Import Git Repository"**
3. Selecciona **`pickspromlb-app/pickspromlb`**
4. Click **"Import"**

### Paso 5.2: Configurar el proyecto

1. **Project Name:** `pickspromlb`
2. **Framework Preset:** Vite
3. **Root Directory:** Click **"Edit"** y selecciona **`frontend`**
4. **Build Command:** `npm run build` (auto-detectado)
5. **Output Directory:** `dist` (auto-detectado)

### Paso 5.3: Variables de entorno

Antes de deployar, expande **"Environment Variables"** y agrega:

```
VITE_SUPABASE_URL=https://xbgoojewccjuhzvxpxqg.supabase.co
VITE_SUPABASE_ANON_KEY=[tu publishable key de Supabase]
VITE_API_URL=https://[tu-url-railway].up.railway.app
```

### Paso 5.4: Deploy

Click **"Deploy"**.

Vercel buildeará. Tomará 1-2 minutos.

Cuando termine, te dará una URL como: `https://pickspromlb.vercel.app`

---

## 🔐 FASE 6: Configurar Login con Google

### Paso 6.1: Habilitar Google Auth en Supabase

1. En Supabase, ve a **Authentication** (en el menú lateral)
2. Click en pestaña **"Providers"**
3. Busca **Google** y click para expandir
4. Click el toggle para **habilitar**

### Paso 6.2: Crear OAuth en Google Cloud

1. Ve a https://console.cloud.google.com/
2. Crea un proyecto nuevo: **"PicksProMLB"**
3. En el menú, ve a **"APIs & Services" → "Credentials"**
4. Click **"+ CREATE CREDENTIALS" → "OAuth client ID"**
5. Configure consent screen primero si te lo pide (datos básicos)
6. **Application type:** Web application
7. **Name:** PicksProMLB
8. **Authorized JavaScript origins:** agrega:
   - `https://pickspromlb.vercel.app`
   - `https://xbgoojewccjuhzvxpxqg.supabase.co`
9. **Authorized redirect URIs:** agrega:
   - `https://xbgoojewccjuhzvxpxqg.supabase.co/auth/v1/callback`
10. Click **"CREATE"**
11. Copia el **Client ID** y **Client Secret**

### Paso 6.3: Pegar credenciales en Supabase

1. Vuelve a Supabase → Authentication → Providers → Google
2. Pega **Client ID** y **Client Secret**
3. Click **"Save"**

### Paso 6.4: Probar login

1. Abre https://pickspromlb.vercel.app
2. Click **"Continuar con Google"**
3. Login con `pickspromlb@gmail.com`
4. ✅ Deberías entrar al dashboard

---

## 🧪 FASE 7: Pruebas y verificación

### Paso 7.1: Probar las APIs (desde tu computadora)

Si tienes Python instalado localmente:

```bash
cd pickspromlb
pip install -r requirements.txt
cp .env.example .env
# Edita .env con tus credenciales
python scripts/test_all.py
```

### Paso 7.2: Verificar logs en Railway

1. En Railway, click en tu servicio
2. Click pestaña **"Deployments"**
3. Click en el deploy activo
4. Revisa los logs en tiempo real

Deberías ver mensajes como:
```
✅ Conectado a Supabase
🤖 Bot iniciado, escuchando comandos...
⏰ Scheduler iniciado
```

### Paso 7.3: Probar el bot manualmente

Abre Telegram y mándale a tu bot:

- `/start` → debe darte la bienvenida
- `/juegos` → debe mostrar juegos del día
- `/picks` → debe mostrar picks (si ya se generaron)
- `/filtros` → debe mostrar efectividad

### Paso 7.4: Trigger manual de análisis

Si no se ha generado picks aún para hoy, puedes forzarlo:

```bash
curl -X POST https://[tu-url-railway].up.railway.app/api/trigger/recolectar
curl -X POST https://[tu-url-railway].up.railway.app/api/trigger/analizar
```

O directamente desde el dashboard web (si agregamos botón).

---

## 🎯 FASE 8: Operación normal del sistema

### El sistema funciona así automáticamente:

1. **7:00 AM ET diario** — Tarea matutina:
   - Procesa resultados del día anterior
   - Detecta horario del primer y último juego de hoy
   - Programa los demás triggers dinámicamente

2. **4 horas antes del primer juego** — Generar listín:
   - Recolecta stats actualizadas
   - Recolecta odds del día
   - Recolecta clima de cada estadio
   - Aplica los 10 filtros
   - Envía JSON a Gemini para análisis
   - Genera picks recomendados
   - Te avisa por Telegram

3. **1 hora antes del primer juego** — Actualizar:
   - Re-verifica odds y pitchers
   - Ajusta picks si algo cambió

4. **2 horas después del último juego** — Resultados:
   - Procesa resultados finales
   - Marca picks como ganados/perdidos
   - Envía resumen del día por Telegram

---

## 🐛 Troubleshooting

### El bot no responde
- Verifica que Railway esté running (no en sleep)
- Verifica `TELEGRAM_BOT_TOKEN` en variables de Railway
- Revisa logs en Railway

### No genera picks
- Verifica que las APIs (Odds, Weather, Gemini) tengan créditos
- Revisa logs para ver el error específico
- Verifica que las tablas en Supabase tengan datos

### Dashboard muestra "No data"
- Verifica `VITE_API_URL` en Vercel apunta a Railway
- Verifica CORS en el backend (debería estar abierto)
- Abre la consola del navegador (F12) y revisa errores

### Error de stats avanzadas (wOBA, wRC+)
- Estas stats requieren `pybaseball` que necesita refinamiento
- Por ahora pueden estar incompletas
- Te ayudo a refinar después de que todo lo demás funcione

---

## 📞 Próximos pasos

Una vez que el sistema esté corriendo:

1. **Refinar el cálculo de stats avanzadas** con pybaseball
2. **Personalizar el dashboard** con tu branding
3. **Agregar más comandos al bot** según uses el sistema
4. **Optimizar el prompt de Gemini** según resultados reales
5. **Migrar a plan pago** de Railway/Vercel cuando se acabe el trial

---

## ⚠️ IMPORTANTE - Seguridad

Después de tener todo funcionando:

1. **Regenera el token de Telegram:** Abre @BotFather, manda `/revoke`, selecciona `@PicksProMLB_bot`, te dará nuevo token. Actualízalo en Railway.

2. **Restringe CORS en producción:** En `app/api/main.py`, cambia `allow_origins=["*"]` por `allow_origins=["https://pickspromlb.vercel.app"]`

3. **No compartas el archivo .env** ni las API keys con nadie.
