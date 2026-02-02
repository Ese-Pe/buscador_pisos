#!/usr/bin/env python3
"""
Servidor Flask para el dashboard y API del bot inmobiliario.
Incluye health checks, keep-alive y ejecución periódica para Render.com.
"""

import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify

# Add root directory to path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

app = Flask(__name__)

# Variable global para el estado del bot
bot_status = {
    "status": "idle",
    "last_run": None,
    "last_run_stats": None,
    "start_time": datetime.now().isoformat(),
    "next_scheduled_run": None
}


# =============================================================================
# DASHBOARD ROUTES
# =============================================================================

@app.route('/')
def dashboard():
    """Dashboard principal."""
    from database import DatabaseManager
    db = DatabaseManager()

    stats = db.get_stats()
    recent_listings = db.search_listings(limit=10)

    # Convert listings to dicts for template
    recent = [l.to_dict() for l in recent_listings]

    return render_template('dashboard.html',
        active_page='dashboard',
        bot_status=bot_status['status'],
        stats=stats,
        recent_listings=recent
    )


@app.route('/listings')
def listings():
    """Página de listados con filtros."""
    from database import DatabaseManager
    db = DatabaseManager()

    # Get filter parameters
    filters = {
        'portal': request.args.get('portal'),
        'city': request.args.get('city'),
        'max_price': request.args.get('max_price', type=int),
        'min_surface': request.args.get('min_surface', type=int),
        'min_bedrooms': request.args.get('min_bedrooms', type=int),
    }

    # Search listings
    results = db.search_listings(
        portal=filters['portal'],
        city=filters['city'],
        max_price=filters['max_price'],
        min_surface=filters['min_surface'],
        min_bedrooms=filters['min_bedrooms'],
        limit=200
    )

    # Convert to dicts
    listings_data = [l.to_dict() for l in results]

    # Get unique portals for filter dropdown
    stats = db.get_stats()
    portals = list(stats.get('by_portal', {}).keys())

    return render_template('listings.html',
        active_page='listings',
        bot_status=bot_status['status'],
        listings=listings_data,
        portals=portals,
        filters=filters
    )


@app.route('/history')
def history():
    """Página de historial de ejecuciones."""
    from database import DatabaseManager
    db = DatabaseManager()

    runs = db.get_run_stats(limit=50)

    # Convert to dicts and calculate duration
    runs_data = []
    for run in runs:
        d = run.to_dict()
        if run.end_time and run.start_time:
            duration = run.end_time - run.start_time
            d['duration_str'] = str(duration).split('.')[0]
        else:
            d['duration_str'] = None
        runs_data.append(d)

    return render_template('history.html',
        active_page='history',
        bot_status=bot_status['status'],
        runs=runs_data
    )


# =============================================================================
# API ROUTES
# =============================================================================

@app.route('/health')
def health():
    """Health check endpoint."""
    return "OK", 200


@app.route('/status')
@app.route('/api/status')
def status():
    """Estado actual del bot."""
    return jsonify(bot_status)


@app.route('/run')
def trigger_run():
    """Dispara una ejecución del bot."""
    global bot_status

    if bot_status["status"] == "running":
        return jsonify({"error": "Bot is already running"}), 409

    test_mode = request.args.get('test') is not None

    thread = threading.Thread(target=run_bot, args=(test_mode,))
    thread.start()

    return jsonify({
        "message": "Bot execution started",
        "test_mode": test_mode
    }), 202


@app.route('/api/listings')
def api_listings():
    """API endpoint para listados."""
    from database import DatabaseManager
    db = DatabaseManager()

    portal = request.args.get('portal')
    limit = request.args.get('limit', 100, type=int)

    results = db.search_listings(portal=portal, limit=limit)
    return jsonify([l.to_dict() for l in results])


@app.route('/api/stats')
def api_stats():
    """API endpoint para estadísticas."""
    from database import DatabaseManager
    db = DatabaseManager()

    return jsonify(db.get_stats())


# =============================================================================
# BOT EXECUTION
# =============================================================================

def run_bot(test_mode=False):
    """Ejecuta el bot."""
    global bot_status

    bot_status["status"] = "running"
    bot_status["last_run"] = datetime.now().isoformat()

    try:
        from main import RealEstateBot
        bot = RealEstateBot()
        stats = bot.run(test_mode=test_mode, max_pages=25)

        bot_status["last_run_stats"] = {
            "total_found": stats.total_listings_found,
            "new_listings": stats.new_listings,
            "errors": stats.errors,
            "duration": str(stats.end_time - stats.start_time) if stats.end_time else None,
            "portal_stats": stats.portal_stats
        }
        bot_status["status"] = "completed"
        print(f"✅ Bot completado - {stats.new_listings} nuevos anuncios")

    except Exception as e:
        bot_status["status"] = "error"
        bot_status["last_run_stats"] = {"error": str(e)}
        print(f"❌ Error ejecutando bot: {e}")


# =============================================================================
# SCHEDULED RUNNER
# =============================================================================

class ScheduledRunner:
    """Ejecuta el bot de forma periódica."""

    def __init__(self, interval_hours=6):
        self.interval_hours = interval_hours
        self.interval_seconds = interval_hours * 3600
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print(f"⏰ Ejecutor periódico iniciado (cada {self.interval_hours}h)")

        # Ejecutar inmediatamente al inicio
        thread = threading.Thread(target=run_bot, daemon=True)
        thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self):
        while self._running:
            next_run = datetime.now().timestamp() + self.interval_seconds
            bot_status["next_scheduled_run"] = datetime.fromtimestamp(next_run).isoformat()
            time.sleep(self.interval_seconds)

            if self._running and bot_status["status"] != "running":
                run_bot()


# =============================================================================
# KEEP ALIVE
# =============================================================================

class KeepAlive:
    """Keep-alive service para Render.com."""

    def __init__(self, service_url: str, interval_minutes: int = 10):
        self.service_url = service_url
        self.interval_seconds = interval_minutes * 60
        self._running = False
        self._thread = None

    def start(self):
        if not self.service_url or self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._ping_loop, daemon=True)
        self._thread.start()
        print(f"💗 Keep-alive iniciado (ping cada {self.interval_seconds // 60} minutos)")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _ping_loop(self):
        import requests

        while self._running:
            time.sleep(self.interval_seconds)
            if not self._running:
                break

            try:
                response = requests.get(f"{self.service_url}/health", timeout=10)
                if response.status_code == 200:
                    print(f"💗 Keep-alive ping exitoso - {datetime.now().strftime('%H:%M:%S')}")
            except Exception as e:
                print(f"⚠️  Keep-alive ping error: {e}")


# =============================================================================
# MAIN
# =============================================================================

scheduled_runner = None
keep_alive = None


def run_server(port=10000, enable_scheduler=True, interval_hours=6, enable_keep_alive=True):
    """Inicia el servidor Flask."""
    global scheduled_runner, keep_alive

    from utils import load_config
    config = load_config('config/config.yaml')
    keep_alive_config = config.get('keep_alive', {})

    # Iniciar keep-alive
    if enable_keep_alive and keep_alive_config.get('enabled', False):
        service_url = os.environ.get('RENDER_SERVICE_URL', '')
        if service_url and '${' not in service_url:
            ping_interval = keep_alive_config.get('ping_interval_minutes', 10)
            keep_alive = KeepAlive(service_url=service_url, interval_minutes=ping_interval)
            keep_alive.start()

    # Iniciar ejecutor periódico
    if enable_scheduler:
        scheduled_runner = ScheduledRunner(interval_hours=interval_hours)
        scheduled_runner.start()

    print(f"🌐 Servidor Flask iniciado")
    print(f"   Puerto: {port}")
    print(f"   Dashboard: http://localhost:{port}/")
    print(f"   Health: http://localhost:{port}/health")
    print(f"   Scheduler: {'habilitado' if enable_scheduler else 'deshabilitado'}")
    print(f"   Keep-alive: {'habilitado' if keep_alive else 'deshabilitado'}")

    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    interval = int(os.environ.get("SCRAPE_INTERVAL_HOURS", 6))
    enable_scheduler = os.environ.get("ENABLE_SCHEDULER", "true").lower() == "true"

    print(f"🚀 Iniciando servidor en puerto {port}")
    run_server(port=port, enable_scheduler=enable_scheduler, interval_hours=interval)
