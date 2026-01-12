"""
Clase base abstracta para todos los scrapers de portales inmobiliarios.
Define la interfaz común y funcionalidades compartidas.
"""

import random
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
            html = self._fetch_page(search_url)
            if not html:
                self.logger.warning(f"No se pudo obtener la página {page}")
                break
            
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
            response = self.session.get(
                url,
                timeout=self.timeout,
                headers=self._get_headers()
            )
            response.raise_for_status()
            
            self._last_request_time = time.time()
            return response.text
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error obteniendo {url}: {e}")
            return None
    
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
    """
    
    requires_selenium = True
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._driver = None
    
    @property
    def driver(self):
        """
        Obtiene o crea una instancia de Selenium WebDriver.
        
        Returns:
            WebDriver configurado
        """
        if self._driver is None:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument(f'--user-agent={random.choice(self.user_agents)}')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            # Intentar usar chromedriver del sistema
            try:
                self._driver = webdriver.Chrome(options=options)
            except Exception:
                # Intentar con webdriver-manager
                try:
                    from webdriver_manager.chrome import ChromeDriverManager
                    service = Service(ChromeDriverManager().install())
                    self._driver = webdriver.Chrome(service=service, options=options)
                except Exception as e:
                    self.logger.error(f"No se pudo inicializar Selenium: {e}")
                    raise
            
            self._driver.implicitly_wait(10)
            self.logger.info("Selenium WebDriver inicializado")
        
        return self._driver
    
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
        """Cierra el WebDriver y la sesión HTTP."""
        if self._driver:
            self._driver.quit()
            self._driver = None
        super().close()
