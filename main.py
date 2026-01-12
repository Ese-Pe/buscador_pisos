#!/usr/bin/env python3
"""
Real Estate Bot - Orquestador Principal

Bot automatizado para monitorizar ofertas de pisos en portales inmobiliarios españoles.
Detecta anuncios nuevos y envía notificaciones por email y Telegram.

Uso:
    python main.py                    # Ejecuta el bot en modo normal
    python main.py --test             # Ejecuta en modo test (sin notificaciones)
    python main.py --profile madrid   # Ejecuta solo un perfil específico
    python main.py --portal tucasa    # Ejecuta solo un portal específico
    python main.py --stats            # Muestra estadísticas
    python main.py --test-notify      # Prueba las notificaciones
"""

import argparse
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Añadir directorio raíz al path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from database import DatabaseManager, Listing, RunStats
from notifiers import EmailNotifier, TelegramNotifier
from scrapers import get_scraper, get_available_portals
from utils import (
    load_config,
    load_filters,
    setup_logger,
    get_logger,
    matches_filter,
    ensure_dir,
)


class RealEstateBot:
    """
    Orquestador principal del bot inmobiliario.
    Coordina los scrapers, la base de datos y las notificaciones.
    """
    
    def __init__(self, config_path: str = "config/config.yaml", filters_path: str = "config/filters.yaml"):
        # Cargar configuración
        self.config = load_config(config_path)
        self.filters = load_filters(filters_path)
        
        # Configurar logging
        log_config = self.config.get('logging', {})
        self.logger = setup_logger(
            name="real_estate_bot",
            log_dir=log_config.get('log_dir', 'logs'),
            level=log_config.get('level', 'INFO'),
        )
        
        # Modo de ejecución
        self.test_mode = self.config.get('general', {}).get('mode') == 'test'
        
        # Inicializar base de datos
        db_path = self.config.get('database', {}).get('path', 'data/listings.db')
        ensure_dir(Path(db_path).parent)
        self.db = DatabaseManager(db_path)
        
        # Notificadores
        self.email_notifier = EmailNotifier(self.config.get('email', {}))
        self.telegram_notifier = TelegramNotifier(self.config.get('telegram', {}))
        
        self.run_stats = None
        self.logger.info("Real Estate Bot inicializado")
    
    def run(self, portals: List[str] = None, profiles: List[str] = None, 
            test_mode: bool = None, max_pages: int = 10) -> RunStats:
        """Ejecuta el bot completo."""
        if test_mode is not None:
            self.test_mode = test_mode
        
        self.logger.info("="*60)
        self.logger.info(f"Iniciando ejecución {'[TEST MODE]' if self.test_mode else ''}")
        self.logger.info(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("="*60)
        
        self.run_stats = RunStats()
        
        # Obtener portales activos
        portals_config = self.config.get('portals', {})
        active_portals = portals or [
            name for name, cfg in portals_config.items()
            if cfg.get('enabled', True)
        ]
        active_portals = sorted(active_portals, key=lambda p: portals_config.get(p, {}).get('priority', 99))
        
        # Obtener perfiles activos
        profiles_config = self.filters.get('profiles', {})
        active_profiles = profiles or [
            name for name, cfg in profiles_config.items()
            if cfg.get('enabled', True)
        ]
        
        self.run_stats.profiles_searched = active_profiles
        self.logger.info(f"Portales: {active_portals}")
        self.logger.info(f"Perfiles: {active_profiles}")
        
        # Resetear flags de nuevos
        self.db.reset_new_flags()
        
        all_new_listings = []
        
        # Ejecutar scraping
        for profile_name in active_profiles:
            profile = profiles_config.get(profile_name, {})
            self.logger.info(f"\n--- Perfil: {profile.get('name', profile_name)} ---")
            
            for portal_name in active_portals:
                try:
                    new_listings = self._scrape_portal(portal_name, profile, max_pages)
                    all_new_listings.extend(new_listings)
                except Exception as e:
                    self.logger.error(f"Error en {portal_name}: {e}")
                    self.run_stats.errors += 1
        
        # Notificaciones
        if all_new_listings:
            self.logger.info(f"\n📬 Enviando notificaciones: {len(all_new_listings)} nuevos")
            self._send_notifications(all_new_listings)
        else:
            self.logger.info("\n✓ No hay anuncios nuevos")
        
        # Finalizar
        self.run_stats.complete(success=True)
        self.db.save_run_stats(self.run_stats)
        self.db.cleanup_old_listings(self.config.get('database', {}).get('retention_days', 90))
        self._print_summary()
        
        return self.run_stats
    
    def _scrape_portal(self, portal_name: str, profile: Dict[str, Any], max_pages: int = 10) -> List[Listing]:
        """Ejecuta el scraping de un portal."""
        self.logger.info(f"Escaneando {portal_name}...")
        
        new_listings = []
        found_count = 0
        error_count = 0
        
        try:
            general_config = self.config.get('general', {})
            scraper = get_scraper(portal_name, general_config)
            
            search_filters = {
                'operation_type': self.filters.get('global', {}).get('operation_type', 'compra'),
                'property_type': self.filters.get('global', {}).get('property_types', ['piso'])[0],
                'location': profile.get('location', {}),
                'price': profile.get('price', {}),
                'surface': profile.get('surface', {}),
                'bedrooms': profile.get('bedrooms', {}),
                'bathrooms': profile.get('bathrooms', {}),
            }
            
            with scraper:
                for listing in scraper.scrape(search_filters, max_pages=max_pages, fetch_details=False):
                    found_count += 1
                    
                    if self.db.is_excluded(listing.id):
                        continue
                    
                    if not matches_filter(listing.__dict__, profile):
                        continue
                    
                    is_new = self.db.save_listing(listing)
                    if is_new:
                        listing.is_new = True
                        new_listings.append(listing)
                        price_str = f"{listing.price:,}€".replace(',', '.') if listing.price else "N/A"
                        self.logger.info(f"  ✨ NUEVO: {listing.title[:40]}... - {price_str}")
        
        except Exception as e:
            self.logger.error(f"Error scrapeando {portal_name}: {e}")
            error_count += 1
        
        self.run_stats.add_portal_stats(portal_name, found_count, len(new_listings), error_count)
        self.logger.info(f"  {portal_name}: {found_count} encontrados, {len(new_listings)} nuevos")
        
        return new_listings
    
    def _send_notifications(self, listings: List[Listing]):
        """Envía notificaciones."""
        if not listings:
            return
        
        if self.email_notifier.is_configured():
            try:
                success = self.email_notifier.send_notification(listings, test_mode=self.test_mode)
                if success:
                    for listing in listings:
                        self.db.record_notification(listing.id, 'email')
            except Exception as e:
                self.logger.error(f"Error email: {e}")
        
        if self.telegram_notifier.is_configured():
            try:
                success = self.telegram_notifier.send_notification(listings, test_mode=self.test_mode)
                if success:
                    for listing in listings:
                        self.db.record_notification(listing.id, 'telegram')
            except Exception as e:
                self.logger.error(f"Error Telegram: {e}")
    
    def _print_summary(self):
        """Imprime resumen de ejecución."""
        if not self.run_stats:
            return
        
        duration = (self.run_stats.end_time - self.run_stats.start_time).total_seconds() if self.run_stats.end_time else 0
        
        self.logger.info("\n" + "="*60)
        self.logger.info("RESUMEN")
        self.logger.info("="*60)
        self.logger.info(f"Duración: {duration:.1f}s")
        self.logger.info(f"Encontrados: {self.run_stats.total_listings_found}")
        self.logger.info(f"Nuevos: {self.run_stats.new_listings}")
        self.logger.info(f"Errores: {self.run_stats.errors}")
        
        if self.run_stats.portal_stats:
            self.logger.info("\nPor portal:")
            for portal, stats in self.run_stats.portal_stats.items():
                self.logger.info(f"  {portal}: {stats['found']} / {stats['new']} nuevos")
        self.logger.info("="*60)
    
    def test_notifications(self):
        """Prueba las notificaciones."""
        self.logger.info("Probando notificaciones...")
        
        test_listing = Listing(
            id="test_123", portal="test", url="https://example.com/test",
            title="Piso de prueba - 3 habitaciones", price=250000,
            city="Madrid", zone="Chamberí", province="Madrid",
            surface=85, bedrooms=3, bathrooms=2,
            has_elevator=True, has_terrace=True,
            description="Anuncio de prueba."
        )
        
        if self.email_notifier.is_configured():
            self.email_notifier.send_notification([test_listing], test_mode=True)
        
        if self.telegram_notifier.is_configured():
            self.telegram_notifier.send_test_message()
    
    def show_stats(self):
        """Muestra estadísticas."""
        stats = self.db.get_stats()
        
        print("\n" + "="*60)
        print("ESTADÍSTICAS")
        print("="*60)
        print(f"Total: {stats['total_listings']}")
        print(f"Activos: {stats['active_listings']}")
        print(f"Nuevos: {stats['new_listings']}")
        
        if stats.get('by_portal'):
            print("\nPor portal:")
            for portal, data in stats['by_portal'].items():
                print(f"  {portal}: {data['total']} ({data['active']} activos)")
        
        if stats.get('last_run'):
            print(f"\nÚltima ejecución: {stats['last_run']['time']}")
        print("="*60 + "\n")


class KeepAlive:
    """Servicio keep-alive para Render.com."""
    
    def __init__(self, config: Dict[str, Any]):
        self.enabled = config.get('enabled', False)
        self.service_url = config.get('service_url', '')
        self.interval = config.get('ping_interval_minutes', 10) * 60
        self._running = False
        self._thread = None
        self.logger = get_logger("keep_alive")
    
    def start(self):
        if not self.enabled or not self.service_url:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._ping_loop, daemon=True)
        self._thread.start()
        self.logger.info(f"Keep-alive iniciado ({self.interval}s)")
    
    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def _ping_loop(self):
        import requests
        while self._running:
            try:
                requests.get(self.service_url, timeout=10)
            except:
                pass
            time.sleep(self.interval)


def main():
    parser = argparse.ArgumentParser(description="Real Estate Bot")
    parser.add_argument('--test', '-t', action='store_true', help='Modo test')
    parser.add_argument('--portal', '-p', type=str, help='Portal específico')
    parser.add_argument('--profile', type=str, help='Perfil específico')
    parser.add_argument('--stats', '-s', action='store_true', help='Ver estadísticas')
    parser.add_argument('--test-notify', action='store_true', help='Probar notificaciones')
    parser.add_argument('--list-portals', action='store_true', help='Listar portales')
    parser.add_argument('--max-pages', type=int, default=5, help='Máx páginas')
    parser.add_argument('--config', default='config/config.yaml', help='Config file')
    parser.add_argument('--keep-alive', action='store_true', help='Keep alive para Render')
    
    args = parser.parse_args()
    
    if args.list_portals:
        print("\nPortales disponibles:")
        for p in get_available_portals():
            print(f"  - {p}")
        return
    
    bot = RealEstateBot(config_path=args.config)
    
    if args.stats:
        bot.show_stats()
        return
    
    if args.test_notify:
        bot.test_notifications()
        return
    
    keep_alive = None
    if args.keep_alive:
        keep_alive = KeepAlive(bot.config.get('keep_alive', {}))
        keep_alive.start()
    
    try:
        portals = [args.portal] if args.portal else None
        profiles = [args.profile] if args.profile else None
        bot.run(portals=portals, profiles=profiles, test_mode=args.test, max_pages=args.max_pages)
    finally:
        if keep_alive:
            keep_alive.stop()


if __name__ == "__main__":
    main()
