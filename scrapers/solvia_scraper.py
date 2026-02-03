"""
Scraper para Solvia - Portal de propiedades bancarias de Sabadell.
https://www.solvia.es

Solvia gestiona activos inmobiliarios del Banco Sabadell.
Requires Selenium due to JavaScript and anti-bot protection.
"""

import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from .base_scraper import SeleniumBaseScraper


class SolviaScraper(SeleniumBaseScraper):
    """
    Scraper para Solvia using Selenium.

    Solvia es el servicer inmobiliario del Banco Sabadell.
    Gestiona una amplia cartera de propiedades bancarias.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.base_url = 'https://www.solvia.es'
        self.name = 'solvia'

    def _fetch_page(self, url: str) -> Optional[str]:
        """Override to add extra wait time for Solvia's JavaScript."""
        if not self._can_fetch(url):
            return None

        self._apply_delay()

        try:
            self.driver.get(url)
            time.sleep(4)

            # Scroll to load lazy content
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            time.sleep(1)

            self._last_request_time = time.time()
            return self.driver.page_source

        except Exception as e:
            self.logger.error(f"Error getting {url}: {e}")
            return None

    def build_search_url(self, filters: Dict[str, Any]) -> str:
        """
        Construye URL de búsqueda de Solvia.

        Formato: /es/comprar/viviendas/{province}
        Ejemplo: /es/comprar/viviendas/zaragoza
        """
        location = filters.get('location', {})
        province = location.get('province', '').lower()

        province = self._normalize_for_url(province)

        operation = filters.get('operation_type', 'compra')
        if operation in ['compra', 'venta']:
            operation_path = 'comprar'
        else:
            operation_path = 'alquilar'

        # Solvia format: /es/comprar/viviendas/{province}
        if province:
            url = f"{self.base_url}/es/{operation_path}/viviendas/{province}"
        else:
            url = f"{self.base_url}/es/{operation_path}/viviendas"

        self.logger.info(f"Solvia search URL: {url}")
        return url

    def _normalize_for_url(self, text: str) -> str:
        """Normaliza texto para URL."""
        if not text:
            return ''

        text = text.lower().strip()

        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'ñ': 'n', 'ü': 'u', 'à': 'a', 'è': 'e', 'ì': 'i',
            'ò': 'o', 'ù': 'u', 'ç': 'c'
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        text = text.replace(' ', '-')
        return text

    def parse_listing_list(self, html: str) -> List[Dict[str, Any]]:
        """Parsea la página de listado de Solvia."""
        soup = BeautifulSoup(html, 'html.parser')
        listings = []

        # Solvia usa tarjetas de activos
        items = soup.find_all('div', class_=re.compile(r'asset-card|property-card|resultado'))

        if not items:
            items = soup.select('.card-inmueble, .listing-item, [data-id]')

        self.logger.debug(f"Solvia: Found {len(items)} items")

        for item in items:
            try:
                listing = self._parse_listing_item(item)
                if listing.get('url'):
                    listings.append(listing)
            except Exception as e:
                self.logger.debug(f"Error parsing Solvia item: {e}")
                continue

        return listings

    def _parse_listing_item(self, item: BeautifulSoup) -> Dict[str, Any]:
        """Extrae datos de un item de Solvia."""
        listing = {}

        # URL
        link = item.find('a', href=re.compile(r'/vivienda|/activo|/inmueble'))
        if not link:
            link = item.find('a')

        if link and link.get('href'):
            listing['url'] = urljoin(self.base_url, link.get('href'))

        # Título
        title_elem = item.find(['h2', 'h3', 'h4'])
        if not title_elem:
            title_elem = item.find(class_=re.compile(r'title|titulo'))
        if title_elem:
            listing['title'] = title_elem.get_text(strip=True)

        # Precio
        price_elem = item.find(class_=re.compile(r'price|precio'))
        if price_elem:
            listing['price'] = price_elem.get_text(strip=True)

        # Ubicación
        location_elem = item.find(class_=re.compile(r'location|ubicacion|localidad'))
        if location_elem:
            listing['city'] = location_elem.get_text(strip=True)

        # Características
        features = item.find_all(class_=re.compile(r'feature|caracteristica|info'))
        for feature in features:
            text = feature.get_text(strip=True).lower()

            if 'm²' in text or 'm2' in text:
                listing['surface'] = text
            elif 'hab' in text or 'dormitorio' in text:
                listing['bedrooms'] = text
            elif 'baño' in text:
                listing['bathrooms'] = text

        # Imagen
        img_elem = item.find('img')
        if img_elem:
            img_src = img_elem.get('src') or img_elem.get('data-src')
            if img_src:
                listing['images'] = [img_src]

        return listing

    def parse_listing_detail(self, html: str, url: str) -> Dict[str, Any]:
        """Parsea la página de detalle."""
        return {}

    def get_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        """Extrae URL de la siguiente página."""
        soup = BeautifulSoup(html, 'html.parser')

        next_link = soup.find('a', class_=re.compile(r'next|siguiente'))

        if not next_link:
            pagination = soup.find(class_=re.compile(r'pagination'))
            if pagination:
                next_link = pagination.find('a', rel='next')

        if next_link and next_link.get('href'):
            return urljoin(self.base_url, next_link.get('href'))

        return None
