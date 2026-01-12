#!/usr/bin/env python3
"""
Servidor HTTP simple para health checks y keep-alive en Render.com.
También puede ejecutar el bot bajo demanda vía webhook.
"""

import json
import os
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Variable global para el estado del bot
bot_status = {
    "status": "idle",
    "last_run": None,
    "last_run_stats": None,
    "start_time": datetime.now().isoformat()
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


def run_server(port=8080):
    """Inicia el servidor HTTP."""
    server = HTTPServer(("0.0.0.0", port), BotHandler)
    print(f"🌐 Servidor iniciado en puerto {port}")
    print(f"   Health check: http://localhost:{port}/health")
    print(f"   Status: http://localhost:{port}/status")
    print(f"   Trigger run: http://localhost:{port}/run")
    server.serve_forever()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    run_server(port)
