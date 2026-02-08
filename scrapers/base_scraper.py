"""
Clase base abstracta para todos los scrapers de portales inmobiliarios.
Define la interfaz común y funcionalidades compartidas.
"""

import random
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from database import Listing
from utils import (
    LoggerMixin,
    clean_price,
    clean_rooms,
    clean_surface,
    generate_listing_id,
    get_logger,
    normalize_url,
    random_delay,
)


# =============================================================================
# SHARED SELENIUM DRIVER MANAGER
# =============================================================================
# Singleton to share a single Chrome instance across all Selenium scrapers
# This dramatically reduces memory usage on constrained environments

class SharedDriverManager:
    """
    Singleton manager for sharing a single Selenium WebDriver across all scrapers.
    This reduces memory usage from ~200MB per driver to ~200MB total.
    """
    _instance = None
    _lock = threading.Lock()
    _driver = None
    _user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_driver(cls, user_agents: List[str] = None):
        """Get or create the shared WebDriver."""
        if user_agents:
            cls._user_agents = user_agents

        if cls._driver is None:
            with cls._lock:
                if cls._driver is None:
                    cls._driver = cls._create_driver()
        return cls._driver

    @classmethod
    def _create_driver(cls):
        """Create a new WebDriver instance."""
        import os
        import platform
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        logger = get_logger("SharedDriver")
        logger.info("🚀 Creating shared Selenium WebDriver...")

        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')

        # Memory optimization for constrained environments
        options.add_argument('--js-flags=--max-old-space-size=128')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-background-networking')
        options.add_argument('--disable-default-apps')
        options.add_argument('--disable-sync')
        options.add_argument('--disable-translate')
        options.add_argument('--metrics-recording-only')
        options.add_argument('--mute-audio')
        options.add_argument('--no-first-run')
        options.add_argument('--safebrowsing-disable-auto-update')

        # Anti-detection
        user_agent = random.choice(cls._user_agents)
        options.add_argument(f'--user-agent={user_agent}')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-infobars')
        options.add_argument('--lang=es-ES')

        # Linux server options
        if platform.system() == 'Linux':
            options.add_argument('--single-process')

            chrome_bin = os.environ.get('CHROME_BIN')
            if chrome_bin and os.path.exists(chrome_bin):
                options.binary_location = chrome_bin
                logger.info(f"Using Chromium from CHROME_BIN: {chrome_bin}")
            else:
                for path in ['/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome']:
                    if os.path.exists(path):
                        options.binary_location = path
                        logger.info(f"Using Chromium at: {path}")
                        break

        # Initialize driver
        driver = None
        chromedriver_env = os.environ.get('CHROMEDRIVER_PATH')
        if chromedriver_env and os.path.exists(chromedriver_env):
            service = Service(chromedriver_env)
            driver = webdriver.Chrome(service=service, options=options)
            logger.info(f"Using chromedriver from CHROMEDRIVER_PATH: {chromedriver_env}")
        else:
            for path in ['/usr/bin/chromedriver', '/usr/lib/chromium/chromedriver']:
                if os.path.exists(path):
                    service = Service(path)
                    driver = webdriver.Chrome(service=service, options=options)
                    logger.info(f"Using chromedriver at: {path}")
                    break

            if driver is None:
                try:
                    driver = webdriver.Chrome(options=options)
                except Exception:
                    from webdriver_manager.chrome import ChromeDriverManager
                    service = Service(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=options)

        if driver is None:
            raise RuntimeError("Failed to initialize Selenium WebDriver")

        driver.implicitly_wait(10)

        # Anti-detection CDP commands
        try:
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['es-ES', 'es', 'en'] });
                    window.chrome = { runtime: {} };
                '''
            })
        except Exception:
            pass

        logger.info("✅ Shared Selenium WebDriver initialized successfully")
        return driver

    @classmethod
    def quit(cls):
        """Quit the shared driver and free resources."""
        if cls._driver is not None:
            with cls._lock:
                if cls._driver is not None:
                    try:
                        cls._driver.quit()
                    except Exception:
                        pass
                    cls._driver = None
                    logger = get_logger("SharedDriver")
                    logger.info("🛑 Shared Selenium WebDriver closed")


class BaseScraper(ABC, LoggerMixin):
    """
    Clase base abstracta para scrapers de portales inmobiliarios.
    
    Todas las implementaciones de scrapers deben heredar de esta clase
    e implementar los métodos abstractos.
    
    Attributes:
        name: Nombre identificador del portal
        base_url: URL base del portal
        config: Configuración del scraper
    """
    
    # Atributos de clase que deben definir las subclases
    name: str = "base"
    base_url: str = ""
    requires_selenium: bool = False
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Inicializa el scraper con la configuración proporcionada.
        
        Args:
            config: Diccionario de configuración
        """
        self.config = config or {}
        self._session = None
        self._robot_parser = None
        self._last_request_time = 0
        
        # Configuración de delays
        self.min_delay = self.config.get('request_delay_min', 3)
        self.max_delay = self.config.get('request_delay_max', 5)
        
        # Configuración de reintentos
        self.max_retries = self.config.get('max_retries', 3)
        self.retry_backoff = self.config.get('retry_backoff_factor', 2)
        
        # Timeout
        self.timeout = self.config.get('request_timeout', 30)
        
        # User agents
        self.user_agents = self.config.get('user_agents', [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ])
        
        # Respetar robots.txt
        self.respect_robots = self.config.get('respect_robots_txt', True)
        
        self.logger.info(f"Scraper inicializado: {self.name}")
    
    # -------------------------------------------------------------------------
    # PROPIEDADES
    # -------------------------------------------------------------------------
    
    @property
    def session(self) -> requests.Session:
        """
        Obtiene o crea una sesión HTTP con reintentos configurados.
        
        Returns:
            Sesión requests configurada
        """
        if self._session is None:
            self._session = requests.Session()
            
            # Configurar reintentos
            retry_strategy = Retry(
                total=self.max_retries,
                backoff_factor=self.retry_backoff,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST"]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
            
            # Headers por defecto
            self._session.headers.update(self._get_headers())
        
        return self._session
    
    @property
    def robot_parser(self) -> Optional[RobotFileParser]:
        """
        Obtiene el parser de robots.txt del portal.
        
        Returns:
            RobotFileParser o None si no se usa
        """
        if not self.respect_robots:
            return None
        
        if self._robot_parser is None:
            self._robot_parser = RobotFileParser()
            robots_url = urljoin(self.base_url, "/robots.txt")
            try:
                self._robot_parser.set_url(robots_url)
                self._robot_parser.read()
                self.logger.debug(f"robots.txt cargado: {robots_url}")
            except Exception as e:
                self.logger.warning(f"No se pudo cargar robots.txt: {e}")
                self._robot_parser = None
        
        return self._robot_parser
    
    # -------------------------------------------------------------------------
    # MÉTODOS ABSTRACTOS (deben implementar las subclases)
    # -------------------------------------------------------------------------
    
    @abstractmethod
    def build_search_url(self, filters: Dict[str, Any]) -> str:
        """
        Construye la URL de búsqueda con los filtros especificados.
        
        Args:
            filters: Diccionario con los filtros de búsqueda
        
        Returns:
            URL de búsqueda
        """
        pass
    
    @abstractmethod
    def parse_listing_list(self, html: str) -> List[Dict[str, Any]]:
        """
        Parsea el HTML de la página de listado y extrae los anuncios.
        
        Args:
            html: Contenido HTML de la página
        
        Returns:
            Lista de diccionarios con datos básicos de cada anuncio
        """
        pass
    
    @abstractmethod
    def parse_listing_detail(self, html: str, url: str) -> Dict[str, Any]:
        """
        Parsea el HTML de la página de detalle de un anuncio.
        
        Args:
            html: Contenido HTML de la página
            url: URL del anuncio
        
        Returns:
            Diccionario con todos los datos del anuncio
        """
        pass
    
    @abstractmethod
    def get_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        """
        Obtiene la URL de la siguiente página de resultados.
        
        Args:
            html: HTML de la página actual
            current_url: URL de la página actual
        
        Returns:
            URL de la siguiente página o None si no hay más
        """
        pass
    
    # -------------------------------------------------------------------------
    # MÉTODOS DE SCRAPING
    # -------------------------------------------------------------------------
    
    def scrape(
        self,
        filters: Dict[str, Any],
        max_pages: int = 10,
        fetch_details: bool = True
    ) -> Generator[Listing, None, None]:
        """
        Ejecuta el scraping completo del portal.
        
        Args:
            filters: Filtros de búsqueda
            max_pages: Número máximo de páginas a scrapear
            fetch_details: Si obtener detalles de cada anuncio
        
        Yields:
            Objetos Listing con los anuncios encontrados
        """
        self.logger.info(f"Iniciando scraping de {self.name}")
        
        search_url = self.build_search_url(filters)
        self.logger.debug(f"URL de búsqueda: {search_url}")
        
        page = 1
        total_found = 0
        
        while search_url and page <= max_pages:
            self.logger.info(f"Procesando página {page}")

            # Obtener página de listado
            try:
                html = self._fetch_page(search_url)
                if not html:
                    self.logger.warning(f"No se pudo obtener la página {page}")
                    break
            except Exception as e:
                # If _fetch_page raises an exception (403, timeout, etc.),
                # re-raise it so it gets caught at the top level and counted as an error
                self.logger.error(f"Error fatal obteniendo página {page}: {e}")
                raise

            # Parsear listado
            listings_data = self.parse_listing_list(html)
            
            if not listings_data:
                self.logger.info(f"No se encontraron anuncios en la página {page}")
                break
            
            self.logger.info(f"Encontrados {len(listings_data)} anuncios en página {page}")
            
            for listing_data in listings_data:
                try:
                    # Obtener detalles si está configurado
                    if fetch_details and listing_data.get('url'):
                        detail_html = self._fetch_page(listing_data['url'])
                        if detail_html:
                            detail_data = self.parse_listing_detail(
                                detail_html, 
                                listing_data['url']
                            )
                            listing_data.update(detail_data)
                    
                    # Crear objeto Listing
                    listing = self._create_listing(listing_data)
                    if listing:
                        total_found += 1
                        yield listing
                        
                except Exception as e:
                    self.logger.error(f"Error procesando anuncio: {e}")
                    continue
            
            # Siguiente página
            search_url = self.get_next_page_url(html, search_url)
            page += 1
            
            if search_url:
                random_delay(self.min_delay, self.max_delay)
        
        self.logger.info(f"Scraping completado: {total_found} anuncios encontrados")
    
    def scrape_listing(self, url: str) -> Optional[Listing]:
        """
        Scrapea un anuncio individual por su URL.
        
        Args:
            url: URL del anuncio
        
        Returns:
            Objeto Listing o None si falla
        """
        html = self._fetch_page(url)
        if not html:
            return None
        
        try:
            data = self.parse_listing_detail(html, url)
            data['url'] = url
            return self._create_listing(data)
        except Exception as e:
            self.logger.error(f"Error scrapeando anuncio {url}: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # MÉTODOS HTTP
    # -------------------------------------------------------------------------
    
    def _fetch_page(self, url: str) -> Optional[str]:
        """
        Obtiene el contenido HTML de una página.

        Args:
            url: URL a obtener

        Returns:
            Contenido HTML o None si falla
        """
        # Verificar robots.txt
        if not self._can_fetch(url):
            self.logger.warning(f"URL bloqueada por robots.txt: {url}")
            return None

        # Aplicar delay entre peticiones
        self._apply_delay()

        try:
            self.logger.debug(f"Fetching URL: {url}")
            response = self.session.get(
                url,
                timeout=self.timeout,
                headers=self._get_headers()
            )

            self.logger.debug(f"Response status: {response.status_code}")
            self.logger.debug(f"Response length: {len(response.text)} bytes")

            response.raise_for_status()

            self._last_request_time = time.time()

            # Log first 500 chars of response for debugging
            if self.logger.level <= 10:  # DEBUG level
                preview = response.text[:500].replace('\n', ' ')
                self.logger.debug(f"Response preview: {preview}...")

            return response.text

        except requests.exceptions.HTTPError as e:
            # Log specific HTTP errors with more detail
            status_code = response.status_code
            if status_code == 403:
                self.logger.error(f"❌ Portal bloqueado (403 Forbidden): {url}")
                self.logger.error(f"   El portal detectó el scraper y bloqueó el acceso. Puede necesitar Selenium o cookies.")
            elif status_code == 404:
                self.logger.warning(f"⚠️  Página no encontrada (404): {url}")
            else:
                self.logger.error(f"HTTP error {status_code} obteniendo {url}: {e}")
            # Raise exception so it gets counted in error statistics
            raise
        except requests.exceptions.Timeout as e:
            self.logger.error(f"Timeout obteniendo {url}: {e}")
            raise
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error obteniendo {url}: {e}")
            raise
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Genera headers HTTP realistas.
        
        Returns:
            Diccionario de headers
        """
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
    
    def _can_fetch(self, url: str) -> bool:
        """
        Verifica si se puede acceder a una URL según robots.txt.
        
        Args:
            url: URL a verificar
        
        Returns:
            True si se puede acceder
        """
        if not self.respect_robots or not self.robot_parser:
            return True
        
        try:
            return self.robot_parser.can_fetch("*", url)
        except Exception:
            return True
    
    def _apply_delay(self):
        """Aplica delay entre peticiones al mismo dominio."""
        elapsed = time.time() - self._last_request_time
        min_wait = self.min_delay
        
        if elapsed < min_wait:
            wait_time = random.uniform(
                min_wait - elapsed,
                self.max_delay - elapsed
            )
            if wait_time > 0:
                time.sleep(wait_time)
    
    # -------------------------------------------------------------------------
    # MÉTODOS DE UTILIDAD
    # -------------------------------------------------------------------------
    
    def _create_listing(self, data: Dict[str, Any]) -> Optional[Listing]:
        """
        Crea un objeto Listing a partir de los datos parseados.
        
        Args:
            data: Diccionario con datos del anuncio
        
        Returns:
            Objeto Listing o None si faltan datos esenciales
        """
        url = data.get('url', '')
        if not url:
            return None
        
        # Generar ID único
        listing_id = generate_listing_id(url, self.name)
        
        # Normalizar URL
        url = normalize_url(url, self.base_url)
        
        # Crear objeto con datos limpios
        try:
            listing = Listing(
                id=listing_id,
                portal=self.name,
                portal_id=data.get('portal_id'),
                url=url,
                
                title=data.get('title', '').strip(),
                description=data.get('description', '').strip(),
                price=clean_price(str(data.get('price', ''))) if data.get('price') else None,
                
                province=data.get('province', '').strip(),
                city=data.get('city', '').strip(),
                zone=data.get('zone', '').strip(),
                address=data.get('address', '').strip(),
                postal_code=data.get('postal_code', '').strip(),
                latitude=data.get('latitude'),
                longitude=data.get('longitude'),
                
                surface=clean_surface(str(data.get('surface', ''))) if data.get('surface') else None,
                bedrooms=clean_rooms(str(data.get('bedrooms', ''))) if data.get('bedrooms') else None,
                bathrooms=clean_rooms(str(data.get('bathrooms', ''))) if data.get('bathrooms') else None,
                floor=data.get('floor'),
                
                has_elevator=data.get('has_elevator'),
                has_parking=data.get('has_parking'),
                has_storage=data.get('has_storage'),
                has_pool=data.get('has_pool'),
                has_terrace=data.get('has_terrace'),
                has_ac=data.get('has_ac'),
                has_heating=data.get('has_heating'),
                is_furnished=data.get('is_furnished'),
                is_exterior=data.get('is_exterior'),
                
                operation_type=data.get('operation_type', 'compra'),
                property_type=data.get('property_type', 'piso'),
                
                publication_date=data.get('publication_date'),
                
                agency=data.get('agency', '').strip(),
                contact_phone=data.get('contact_phone', '').strip(),
                images=data.get('images', []),
                raw_data=data.get('raw_data', {}),
            )
            
            return listing
            
        except Exception as e:
            self.logger.error(f"Error creando Listing: {e}")
            return None
    
    def close(self):
        """Cierra la sesión HTTP."""
        if self._session:
            self._session.close()
            self._session = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
    
    def __repr__(self) -> str:
        return self.__str__()


class SeleniumBaseScraper(BaseScraper):
    """
    Clase base para scrapers que requieren Selenium.
    Extiende BaseScraper con soporte para JavaScript.

    Uses SharedDriverManager to share a single Chrome instance across all
    Selenium scrapers, dramatically reducing memory usage.
    """

    requires_selenium = True

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._owns_driver = False  # We don't own the driver, SharedDriverManager does

    @property
    def driver(self):
        """
        Get the shared WebDriver instance.

        Returns:
            WebDriver configurado (shared across all Selenium scrapers)
        """
        return SharedDriverManager.get_driver(self.user_agents)

    def _fetch_page(self, url: str) -> Optional[str]:
        """
        Obtiene el contenido HTML usando Selenium.

        Args:
            url: URL a obtener

        Returns:
            Contenido HTML o None si falla
        """
        if not self._can_fetch(url):
            self.logger.warning(f"URL bloqueada por robots.txt: {url}")
            return None

        self._apply_delay()

        try:
            self.driver.get(url)

            # Esperar a que cargue el contenido dinámico
            time.sleep(2)

            self._last_request_time = time.time()
            return self.driver.page_source

        except Exception as e:
            self.logger.error(f"Error obteniendo {url} con Selenium: {e}")
            return None

    def close(self):
        """Close HTTP session. Does NOT close the shared WebDriver."""
        # Don't close the shared driver - let SharedDriverManager handle it
        super().close()
