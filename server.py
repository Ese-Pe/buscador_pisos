#!/usr/bin/env python3
"""
Servidor HTTP simple para health checks y keep-alive en Render.com.
También puede ejecutar el bot bajo demanda vía webhook.
Con modo de ejecución periódica automática.
"""

import json
import os
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Variable global para el estado del bot
bot_status = {
    "status": "idle",
    "last_run": None,
    "last_run_stats": None,
    "start_time": datetime.now().isoformat(),
    "next_scheduled_run": None
}


class BotHandler(BaseHTTPRequestHandler):
    """Handler HTTP para el bot."""
    
    def do_GET(self):
        """Maneja peticiones GET."""
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/" or path == "/health":
            self._send_health()
        elif path == "/status":
            self._send_status()
        elif path == "/run":
            self._trigger_run(parsed.query)
        else:
            self._send_404()
    
    def do_POST(self):
        """Maneja peticiones POST (para webhooks)."""
        if self.path == "/webhook/run":
            self._trigger_run("")
        else:
            self._send_404()
    
    def _send_health(self):
        """Responde al health check."""
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
    
    def _send_status(self):
        """Envía el estado actual del bot."""
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(bot_status, indent=2).encode())
    
    def _send_404(self):
        """Respuesta 404."""
        self.send_response(404)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Not Found")
    
    def _trigger_run(self, query_string):
        """Dispara una ejecución del bot."""
        global bot_status
        
        if bot_status["status"] == "running":
            self.send_response(409)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": "Bot is already running"
            }).encode())
            return
        
        # Parsear parámetros
        params = parse_qs(query_string)
        test_mode = "test" in params
        
        # Ejecutar en hilo separado
        thread = threading.Thread(
            target=self._run_bot,
            args=(test_mode,)
        )
        thread.start()
        
        self.send_response(202)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "message": "Bot execution started",
            "test_mode": test_mode
        }).encode())
    
    def _run_bot(self, test_mode=False):
        """Ejecuta el bot."""
        global bot_status
        
        bot_status["status"] = "running"
        bot_status["last_run"] = datetime.now().isoformat()
        
        try:
            from main import RealEstateBot
            bot = RealEstateBot()
            stats = bot.run(test_mode=test_mode)
            
            bot_status["last_run_stats"] = {
                "total_found": stats.total_listings_found,
                "new_listings": stats.new_listings,
                "errors": stats.errors,
                "duration": str(stats.end_time - stats.start_time) if stats.end_time else None
            }
            bot_status["status"] = "completed"
            
        except Exception as e:
            bot_status["status"] = "error"
            bot_status["last_run_stats"] = {"error": str(e)}
    
    def log_message(self, format, *args):
        """Silencia los logs por defecto."""
        pass


class ScheduledRunner:
    """Ejecuta el bot de forma periódica."""

    def __init__(self, interval_hours=6):
        self.interval_hours = interval_hours
        self.interval_seconds = interval_hours * 3600
        self._running = False
        self._thread = None

    def start(self):
        """Inicia el ejecutor periódico."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print(f"⏰ Ejecutor periódico iniciado (cada {self.interval_hours}h)")

        # Ejecutar inmediatamente al inicio
        self._schedule_immediate_run()

    def stop(self):
        """Detiene el ejecutor periódico."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _schedule_immediate_run(self):
        """Programa una ejecución inmediata."""
        thread = threading.Thread(target=self._run_bot, daemon=True)
        thread.start()

    def _run_loop(self):
        """Loop principal del ejecutor."""
        while self._running:
            next_run = datetime.now().timestamp() + self.interval_seconds
            bot_status["next_scheduled_run"] = datetime.fromtimestamp(next_run).isoformat()

            # Esperar hasta la próxima ejecución
            time.sleep(self.interval_seconds)

            if self._running and bot_status["status"] != "running":
                self._run_bot()

    def _run_bot(self):
        """Ejecuta el bot."""
        global bot_status

        if bot_status["status"] == "running":
            print("⚠️ Bot ya está ejecutándose, saltando ejecución programada")
            return

        bot_status["status"] = "running"
        bot_status["last_run"] = datetime.now().isoformat()

        try:
            print(f"🤖 Ejecutando bot programado - {datetime.now().isoformat()}")
            from main import RealEstateBot
            bot = RealEstateBot()
            stats = bot.run(test_mode=False)

            bot_status["last_run_stats"] = {
                "total_found": stats.total_listings_found,
                "new_listings": stats.new_listings,
                "errors": stats.errors,
                "duration": str(stats.end_time - stats.start_time) if stats.end_time else None
            }
            bot_status["status"] = "completed"
            print(f"✅ Bot completado - {stats.new_listings} nuevos anuncios")

        except Exception as e:
            bot_status["status"] = "error"
            bot_status["last_run_stats"] = {"error": str(e)}
            print(f"❌ Error ejecutando bot: {e}")


# Instancia global del ejecutor periódico
scheduled_runner = None


def run_server(port=8080, enable_scheduler=True, interval_hours=6):
    """Inicia el servidor HTTP."""
    global scheduled_runner

    # Iniciar ejecutor periódico
    if enable_scheduler:
        scheduled_runner = ScheduledRunner(interval_hours=interval_hours)
        scheduled_runner.start()

    server = HTTPServer(("0.0.0.0", port), BotHandler)
    print(f"🌐 Servidor HTTP iniciado correctamente")
    print(f"   Puerto: {port}")
    print(f"   Host: 0.0.0.0 (escuchando en todas las interfaces)")
    print(f"   Health check: http://localhost:{port}/health")
    print(f"   Status: http://localhost:{port}/status")
    print(f"   Trigger run: http://localhost:{port}/run")
    print(f"   Scheduler: {'habilitado' if enable_scheduler else 'deshabilitado'} ({interval_hours}h)")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo servidor...")
        if scheduled_runner:
            scheduled_runner.stop()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    # Ejecutar cada 6 horas por defecto (configurable vía env var)
    interval = int(os.environ.get("SCRAPE_INTERVAL_HOURS", 6))
    enable_scheduler = os.environ.get("ENABLE_SCHEDULER", "true").lower() == "true"

    print(f"🚀 Iniciando servidor en puerto {port}")
    print(f"📊 Variables de entorno:")
    print(f"   PORT={port}")
    print(f"   SCRAPE_INTERVAL_HOURS={interval}")
    print(f"   ENABLE_SCHEDULER={enable_scheduler}")

    run_server(port=port, enable_scheduler=enable_scheduler, interval_hours=interval)
