"""
Módulo de scrapers para portales inmobiliarios.
"""

from .base_scraper import BaseScraper, SeleniumBaseScraper
from .tucasa_scraper import TucasaScraper
from .yaencontre_scraper import YaencontreScraper
from .bienici_scraper import BieniciScraper
from .idealista_scraper import IdealistaScraper
from .fotocasa_scraper import FotocasaScraper
from .pisos_scraper import PisosScraper
from .habitaclia_scraper import HabitacliaScraper
from .altamira_scraper import AltamiraScraper
from .solvia_scraper import SolviaScraper
from .haya_scraper import HayaScraper
from .generic_scraper import GenericScraper, create_portal_scraper, PORTAL_CONFIGS

# Mapeo de nombres a clases de scrapers
SCRAPER_CLASSES = {
    # Agregadores principales (Selenium)
    'tucasa': TucasaScraper,
    'idealista': IdealistaScraper,
    'fotocasa': FotocasaScraper,
    'pisos': PisosScraper,
    'habitaclia': HabitacliaScraper,
    'yaencontre': YaencontreScraper,
    'bienici': BieniciScraper,
    # Portales bancarios (Selenium)
    'altamira': AltamiraScraper,
    'solvia': SolviaScraper,
    'haya': HayaScraper,
    # Otros portales bancarios (GenericScraper fallback)
    'servihabitat': lambda config: create_portal_scraper('servihabitat', config),
    'aliseda': lambda config: create_portal_scraper('aliseda', config),
    'anticipa': lambda config: create_portal_scraper('anticipa', config),
    'bbva_valora': lambda config: create_portal_scraper('bbva_valora', config),
    'bankinter': lambda config: create_portal_scraper('bankinter', config),
    'kutxabank': lambda config: create_portal_scraper('kutxabank', config),
    'cajamar': lambda config: create_portal_scraper('cajamar', config),
    'ibercaja': lambda config: create_portal_scraper('ibercaja', config),
    'comprarcasa': lambda config: create_portal_scraper('comprarcasa', config),
}


def get_scraper(portal_name: str, config: dict = None) -> BaseScraper:
    """
    Obtiene una instancia del scraper para un portal.
    
    Args:
        portal_name: Nombre del portal
        config: Configuración general
    
    Returns:
        Instancia del scraper
    
    Raises:
        ValueError: Si el portal no está soportado
    """
    portal_name = portal_name.lower()
    
    if portal_name not in SCRAPER_CLASSES:
        raise ValueError(f"Portal no soportado: {portal_name}. "
                        f"Portales disponibles: {list(SCRAPER_CLASSES.keys())}")
    
    scraper_class = SCRAPER_CLASSES[portal_name]
    
    # Si es una función (para portales genéricos), llamarla
    if callable(scraper_class) and not isinstance(scraper_class, type):
        return scraper_class(config)
    
    return scraper_class(config)


def get_available_portals() -> list:
    """
    Devuelve la lista de portales soportados.
    
    Returns:
        Lista de nombres de portales
    """
    return list(SCRAPER_CLASSES.keys())


__all__ = [
    'BaseScraper',
    'SeleniumBaseScraper',
    'TucasaScraper',
    'IdealistaScraper',
    'FotocasaScraper',
    'PisosScraper',
    'HabitacliaScraper',
    'AltamiraScraper',
    'SolviaScraper',
    'HayaScraper',
    'YaencontreScraper',
    'BieniciScraper',
    'GenericScraper',
    'create_portal_scraper',
    'PORTAL_CONFIGS',
    'SCRAPER_CLASSES',
    'get_scraper',
    'get_available_portals',
]
