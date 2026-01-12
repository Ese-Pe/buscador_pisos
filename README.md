# 🏠 Real Estate Bot

Bot automatizado para monitorizar ofertas de pisos en portales inmobiliarios españoles. Detecta anuncios nuevos y envía notificaciones por email y Telegram.

## ✨ Características

- **Multi-portal**: Soporta 15+ portales inmobiliarios (agregadores y bancarios)
- **Filtros avanzados**: Ubicación, precio, superficie, habitaciones, características
- **Notificaciones**: Email (SMTP) y Telegram
- **Base de datos local**: SQLite para tracking de anuncios
- **Anti-detección**: User-agents rotativos, delays aleatorios, respeto de robots.txt
- **Keep-alive**: Soporte para Render.com (plan gratuito)
- **Fácilmente extensible**: Arquitectura modular para añadir nuevos portales

## 📋 Portales Soportados

### Agregadores
- ✅ Tucasa (tucasa.com)
- ✅ Bienici (bienici.com)
- ✅ Yaencontre (yaencontre.com)

### Portales Bancarios
- ✅ Altamira
- ✅ Haya Real Estate
- ✅ Solvia
- ✅ Anticipa
- ✅ Servihabitat
- ✅ Aliseda
- ✅ BBVA Valora
- ✅ Bankinter Habitat
- ✅ Kutxabank
- ✅ Ibercaja Orienta
- ✅ Cajamar
- ✅ Comprarcasa

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/buscador_pisos.git
cd buscador_pisos
```

### 2. Crear entorno virtual

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar credenciales

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales:

```env
# Email
SMTP_USERNAME=tu-email@gmail.com
SMTP_PASSWORD=tu-contraseña-de-aplicacion

# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjkl...
TELEGRAM_CHAT_IDS=123456789
```

### 5. Configurar búsquedas

Edita `config/filters.yaml` para definir tus perfiles de búsqueda:

```yaml
profiles:
  madrid_centro:
    enabled: true
    location:
      province: "Madrid"
      city: "Madrid"
      zones: ["Centro", "Chamberí"]
    price:
      min: 150000
      max: 350000
    surface:
      min: 60
    bedrooms:
      min: 2
```

## 📖 Uso

### Ejecutar el bot

```bash
# Modo normal
python main.py

# Modo test (sin enviar notificaciones)
python main.py --test

# Solo un portal
python main.py --portal tucasa

# Solo un perfil
python main.py --profile madrid_centro

# Ver estadísticas
python main.py --stats

# Probar notificaciones
python main.py --test-notify

# Listar portales disponibles
python main.py --list-portals
```

### Programar ejecución con cron

```bash
# Editar crontab
crontab -e

# Añadir líneas para ejecutar a las 09:00 y 21:30
0 9 * * * cd /ruta/al/bot && /ruta/al/venv/bin/python main.py >> logs/cron.log 2>&1
30 21 * * * cd /ruta/al/bot && /ruta/al/venv/bin/python main.py >> logs/cron.log 2>&1
```

## ☁️ Despliegue en Render.com

### 1. Crear nuevo Web Service

1. Ve a [Render.com](https://render.com) y crea una cuenta
2. Conecta tu repositorio de GitHub
3. Selecciona "Web Service"

### 2. Configuración del servicio

- **Environment**: Python 3
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python main.py --keep-alive`

### 3. Variables de entorno

Añade en el panel de Render:

```
SMTP_USERNAME=tu-email@gmail.com
SMTP_PASSWORD=tu-contraseña
TELEGRAM_BOT_TOKEN=tu-token
TELEGRAM_CHAT_IDS=tu-chat-id
RENDER_SERVICE_URL=https://tu-servicio.onrender.com
```

### 4. Cron Jobs

En Render, crea dos Cron Jobs:
- **09:00**: `python main.py`
- **21:30**: `python main.py`

## 📧 Configuración de Email (Gmail)

Para usar Gmail necesitas una "Contraseña de aplicación":

1. Ve a [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Selecciona "Correo" y "Otro dispositivo"
3. Copia la contraseña generada y úsala en `SMTP_PASSWORD`

## 🤖 Configuración de Telegram

### 1. Crear un bot

1. Habla con [@BotFather](https://t.me/BotFather) en Telegram
2. Envía `/newbot`
3. Sigue las instrucciones y guarda el token

### 2. Obtener tu Chat ID

1. Habla con [@userinfobot](https://t.me/userinfobot)
2. Te responderá con tu ID

### 3. Configurar el bot

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
TELEGRAM_CHAT_IDS=123456789  # Múltiples: 123,456,789
```

## 📁 Estructura del Proyecto

```
real-estate-bot/
├── config/
│   ├── config.yaml       # Configuración general
│   └── filters.yaml      # Filtros de búsqueda
├── scrapers/
│   ├── base_scraper.py   # Clase base abstracta
│   ├── tucasa_scraper.py
│   ├── yaencontre_scraper.py
│   ├── bienici_scraper.py
│   └── generic_scraper.py  # Para portales bancarios
├── database/
│   ├── models.py         # Modelos de datos
│   └── db_manager.py     # Gestor SQLite
├── notifiers/
│   ├── email_notifier.py
│   └── telegram_notifier.py
├── utils/
│   ├── logger.py
│   └── helpers.py
├── main.py               # Punto de entrada
├── requirements.txt
└── README.md
```

## 🔧 Añadir un Nuevo Portal

1. Crea un nuevo archivo en `scrapers/`:

```python
from .base_scraper import BaseScraper

class MiPortalScraper(BaseScraper):
    name = "mi_portal"
    base_url = "https://www.miportal.com"
    
    def build_search_url(self, filters):
        # Implementar
        pass
    
    def parse_listing_list(self, html):
        # Implementar
        pass
    
    def parse_listing_detail(self, html, url):
        # Implementar
        pass
    
    def get_next_page_url(self, html, current_url):
        # Implementar
        pass
```

2. Regístralo en `scrapers/__init__.py`
3. Añádelo a `config/config.yaml`

## ⚠️ Consideraciones Legales

- Este bot es para **uso personal y no comercial**
- Respeta los términos de servicio de cada portal
- El bot incluye delays y respeta `robots.txt`
- No uses el bot para scraping masivo o comercial

## 🐛 Solución de Problemas

### El bot no encuentra anuncios
- Verifica que los filtros no sean demasiado restrictivos
- Algunos portales pueden haber cambiado su estructura HTML
- Ejecuta con `--test` para ver los logs detallados

### Error de autenticación en email
- Asegúrate de usar una "Contraseña de aplicación" de Google
- Verifica que la verificación en 2 pasos esté activada

### Telegram no envía mensajes
- Verifica el token del bot
- Asegúrate de haber iniciado una conversación con el bot
- Comprueba que el Chat ID es correcto

## 📝 Licencia

MIT License - Ver [LICENSE](LICENSE) para más detalles.

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor, abre un issue primero para discutir los cambios propuestos.
