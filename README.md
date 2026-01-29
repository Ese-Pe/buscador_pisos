# 🏠 Real Estate Bot

Bot automatizado para monitorizar ofertas de pisos en portales inmobiliarios españoles. Detecta anuncios nuevos y envía notificaciones por Telegram.

## ✨ Características

- **Multi-portal**: Soporta 15+ portales inmobiliarios (agregadores y bancarios)
- **Tucasa activo**: Portal principal funcionando (otros requieren Selenium)
- **Filtros avanzados**: Ubicación, precio, superficie, habitaciones, características
- **Notificaciones Telegram**: Alertas instantáneas de nuevas propiedades
- **Base de datos local**: SQLite para tracking de anuncios
- **Ejecución programada**: Runs automáticos cada 6 horas
- **Keep-alive para Render**: Previene spin-down en plan gratuito
- **Anti-detección**: User-agents rotativos, delays aleatorios

## 📋 Portales Soportados

### Actualmente Funcionando
- ✅ **Tucasa** (tucasa.com) - Portal principal, 40+ listados

### Disponibles para Selenium (futuro)
- 🔄 Idealista, Fotocasa, Pisos.com (requieren Selenium)
- 🔄 Yaencontre, Bienici

### Portales Bancarios
- 🔄 Altamira, Haya, Solvia, Aliseda (requieren Selenium)
- 🔄 Anticipa, Servihabitat, BBVA Valora
- 🔄 Bankinter, Kutxabank, Ibercaja, Cajamar

> **Nota**: Los portales marcados con 🔄 están implementados pero deshabilitados por protección anti-bot. Se pueden activar implementando Selenium.

## 🚀 Despliegue en Render.com (Recomendado)

### 1. Preparar el Repositorio

1. Fork o clona este repositorio
2. Conecta tu GitHub a Render.com

### 2. Crear Web Service

1. Ve a [Render.com](https://render.com)
2. Click "New" → "Web Service"
3. Conecta tu repositorio
4. Configuración:
   - **Name**: `buscador-pisos`
   - **Region**: Frankfurt (o tu región)
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python server.py`

### 3. Variables de Entorno (CRÍTICO)

En Render Dashboard → Environment, añade:

```
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjkl...
TELEGRAM_CHAT_IDS=123456789
RENDER_SERVICE_URL=https://buscador-pisos.onrender.com
```

⚠️ **`RENDER_SERVICE_URL` es ESENCIAL** para el keep-alive. Sin ella, el servicio se apagará después de 15 minutos.

### 4. Verificar Despliegue

Después del despliegue, visita:
- Health check: `https://buscador-pisos.onrender.com/health`
- Status: `https://buscador-pisos.onrender.com/status`
- Trigger manual: `https://buscador-pisos.onrender.com/run`

## 🤖 Configuración de Telegram

### 1. Crear un Bot

1. Abre Telegram y busca [@BotFather](https://t.me/BotFather)
2. Envía `/newbot`
3. Sigue las instrucciones
4. Guarda el **token** que te da

### 2. Obtener tu Chat ID

**Opción A - Con bot:**
1. Busca [@userinfobot](https://t.me/userinfobot) en Telegram
2. Envíale cualquier mensaje
3. Te responderá con tu Chat ID

**Opción B - Con API:**
1. Envía un mensaje a tu bot
2. Visita (reemplaza `<TOKEN>`):
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
3. Busca `"chat":{"id":XXXXXXX}`

### 3. Iniciar el Bot

1. Busca tu bot en Telegram
2. Envíale `/start`
3. Ahora puede enviarte mensajes

## 🔧 Configuración de Búsquedas

Edita `config/filters.yaml` para tus preferencias:

```yaml
profiles:
  perfil_zaragoza:
    enabled: true
    name: "Zaragoza Centro"

    location:
      province: "Zaragoza"
      city: "Zaragoza"

    price:
      min: 0
      max: 315000

    surface:
      min: 90

    bedrooms:
      min: 3

    features:
      elevator: true
      parking: true
```

## 📊 Monitorización

### Endpoints Disponibles

```bash
# Verificar servicio activo
curl https://buscador-pisos.onrender.com/health

# Ver estado y próxima ejecución
curl https://buscador-pisos.onrender.com/status

# Trigger ejecución manual
curl https://buscador-pisos.onrender.com/run
```

### Respuesta de Status

```json
{
  "status": "completed",
  "last_run": "2026-01-27T13:18:04",
  "last_run_stats": {
    "total_found": 40,
    "new_listings": 9,
    "errors": 0,
    "duration": "0:00:31",
    "portal_stats": {
      "tucasa": {
        "found": 20,
        "new": 5,
        "errors": 0
      }
    }
  },
  "next_scheduled_run": "2026-01-27T19:18:04"
}
```

## 🔍 Verificar Keep-Alive

El keep-alive previene que Render apague el servicio. Verifica que funcione:

### En Render Logs (Dashboard → Logs):

```
🌐 Servidor HTTP iniciado correctamente
   Keep-alive: habilitado
💗 Keep-alive iniciado (ping cada 10 minutos)
⏰ Ejecutor periódico iniciado (cada 6h)
```

Cada 10 minutos verás:
```
💗 Keep-alive ping exitoso - HH:MM:SS
```

Si NO ves estos mensajes:
1. Verifica que `RENDER_SERVICE_URL` esté configurado
2. Verifica que el valor sea correcto (tu URL de Render)
3. Redeploy el servicio

## 🐛 Solución de Problemas

### Bot no ejecuta automáticamente cada 6 horas

**Causa**: Keep-alive no está funcionando, el servicio se apaga.

**Solución**:
1. Añade `RENDER_SERVICE_URL` en Environment variables
2. Valor: `https://buscador-pisos.onrender.com` (tu URL)
3. Redeploy automáticamente
4. Verifica logs para "Keep-alive iniciado"

### No recibo notificaciones de Telegram

**Causa 1: Chat ID incorrecto**
- Verifica tu Chat ID con @userinfobot
- Actualiza `TELEGRAM_CHAT_IDS` en Render

**Causa 2: Bot no iniciado**
- Envía `/start` a tu bot en Telegram

**Causa 3: Token incorrecto**
- Verifica `TELEGRAM_BOT_TOKEN` en Render
- Obtén token actual de @BotFather

### Servicio muestra "Sleeping" en Render

El keep-alive no está funcionando:
1. Asegúrate que `RENDER_SERVICE_URL` existe
2. Espera 10 minutos para primer ping
3. Verifica logs para pings exitosos
4. Si falla, redeploy el servicio

### Bot encuentra 0 propiedades

**Filtros muy restrictivos**:
- Reduce requisitos (ej: quita elevator/parking)
- Aumenta rango de precio
- Reduce superficie mínima

**Portal caído**:
- Verifica que Tucasa.com esté accesible
- Revisa logs para errores específicos

## 📱 Notificaciones Telegram

Cada vez que se encuentren propiedades nuevas, recibirás:

```
🏠 9 Nuevos Pisos Encontrados

📍 Oliver-Valdefierro
💰 220.000€
📐 90 m² | 🛏️ 3 hab | 🚿 1 baño
🔗 Ver detalles

📍 Centro
💰 315.000€
📐 120 m² | 🛏️ 3 hab | 🚿 2 baños
🔗 Ver detalles
```

## 🕐 Funcionamiento Automático

Una vez desplegado correctamente:

```
00:00 → Bot se ejecuta (startup)
00:10 → Keep-alive ping ✓
00:20 → Keep-alive ping ✓
...
06:00 → Bot se ejecuta automáticamente ✓
06:00 → 📱 Notificación Telegram (si hay nuevas)
06:10 → Keep-alive ping ✓
...
12:00 → Bot se ejecuta automáticamente ✓
18:00 → Bot se ejecuta automáticamente ✓
00:00 → Bot se ejecuta automáticamente ✓
```

**Sin intervención manual necesaria** 🎉

## 📁 Estructura del Proyecto

```
buscador_pisos/
├── config/
│   ├── config.yaml       # Configuración general y portales
│   └── filters.yaml      # Filtros de búsqueda y perfiles
├── scrapers/
│   ├── base_scraper.py   # Clase base abstracta
│   ├── tucasa_scraper.py # ✅ Funcionando
│   ├── idealista_scraper.py # 🔄 Necesita Selenium
│   ├── fotocasa_scraper.py  # 🔄 Necesita Selenium
│   ├── pisos_scraper.py     # 🔄 Necesita Selenium
│   ├── yaencontre_scraper.py # 🔄 Necesita Selenium
│   ├── bienici_scraper.py    # 🔄 Necesita Selenium
│   └── generic_scraper.py  # Para portales bancarios
├── database/
│   ├── models.py         # Modelos de datos
│   └── db_manager.py     # Gestor SQLite
├── notifiers/
│   └── telegram_notifier.py
├── utils/
│   ├── logger.py
│   └── helpers.py
├── main.py               # Bot runner
├── server.py             # HTTP server + scheduler + keep-alive
├── requirements.txt
└── README.md
```

## 🔧 Desarrollo Local

### Instalación

```bash
git clone <tu-repo>
cd buscador_pisos
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

### Configuración Local

Crea `.env`:
```env
TELEGRAM_BOT_TOKEN=your-token
TELEGRAM_CHAT_IDS=your-chat-id
```

### Ejecutar

```bash
# Servidor con scheduler (recomendado)
python server.py

# Ejecución única
python main.py

# Modo test (sin notificaciones)
python main.py --test

# Listar portales
python main.py --list-portals
```

## 🚀 Futuras Mejoras

- [ ] Implementar Selenium para Idealista, Fotocasa, Pisos.com
- [ ] Añadir más portales regionales
- [ ] Dashboard web para gestión
- [ ] Filtros por zonas específicas
- [ ] Histórico de precios

## ⚠️ Consideraciones Legales

- Este bot es para **uso personal y no comercial**
- Respeta los términos de servicio de cada portal
- El bot incluye delays y respeta buenas prácticas
- No uses para scraping masivo o comercial
- Los datos son públicos y accesibles manualmente

## 📝 Licencia

MIT License - Ver [LICENSE](LICENSE) para más detalles.

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor, abre un issue primero para discutir los cambios propuestos.

---

**Desarrollado por Claude Code** 🤖
