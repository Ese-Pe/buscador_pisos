"""
Scraper para Altamira Inmuebles - Portal de propiedades bancarias.
https://www.altamirainmuebles.com

Altamira gestiona activos inmobiliarios de Santander y otros bancos.
Requires Selenium due to heavy JavaScript and anti-bot protection.
"""

import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from .base_scraper import SeleniumBaseScraper


class AltamiraScraper(SeleniumBaseScraper):
    """
    Scraper para Altamira Inmuebles using Selenium.

    Altamira es un servicer inmobiliario que gestiona activos de bancos
    como Santander. Suelen tener propiedades a precios por debajo de mercado.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.base_url = 'https://www.altamirainmuebles.com'
        self.name = 'altamira'

    def _fetch_page(self, url: str) -> Optional[str]:
        """
        Override to add extra wait time for Altamira's heavy JavaScript.
        """
        if not self._can_fetch(url):
            return None

        self._apply_delay()

        try:
            self.driver.get(url)

            # Altamira needs more time to load JavaScript
            time.sleep(4)

            # Scroll to trigger lazy loading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            time.sleep(1)

            self._last_request_time = time.time()
            return self.driver.page_source

        except Exception as e:
            self.logger.error(f"Error getting {url} with Selenium: {e}")
            return None

    def build_search_url(self, filters: Dict[str, Any]) -> str:
        """
        Construye URL de búsqueda de Altamira.

        Formato: /venta-viviendas/{province}
        Ejemplo: /venta-viviendas/zaragoza
        """
        location = filters.get('location', {})
        province = location.get('province', '').lower()

        province = self._normalize_for_url(province)

        operation = filters.get('operation_type', 'compra')
        if operation in ['compra', 'venta']:
            operation_path = 'venta'
        else:
            operation_path = 'alquiler'

        # Construir URL - Altamira format: /venta-viviendas/{province}
        if province:
            url = f"{self.base_url}/{operation_path}-viviendas/{province}"
        else:
            url = f"{self.base_url}/{operation_path}-viviendas"

        self.logger.info(f"Altamira search URL: {url}")
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
        """Parsea la página de listado de Altamira."""
        soup = BeautifulSoup(html, 'html.parser')
        listings = []

        # Altamira usa tarjetas de propiedad
        items = soup.find_all('div', class_=re.compile(r'property-card|asset-card|inmueble'))

        if not items:
            items = soup.select('.card, .listing-item, [data-asset-id]')

        self.logger.debug(f"Altamira: Found {len(items)} items")

        for item in items:
            try:
                listing = self._parse_listing_item(item)
                if listing.get('url'):
                    listings.append(listing)
            except Exception as e:
                self.logger.debug(f"Error parsing Altamira item: {e}")
                continue

        return listings

    def _parse_listing_item(self, item: BeautifulSoup) -> Dict[str, Any]:
        """Extrae datos de un item de Altamira."""
        listing = {}

        # URL
        link = item.find('a', href=re.compile(r'/inmueble|/asset|/vivienda'))
        if not link:
            link = item.find('a')

        if link and link.get('href'):
            listing['url'] = urljoin(self.base_url, link.get('href'))

        # Título
        title_elem = item.find(['h2', 'h3', 'h4'], class_=re.compile(r'title|nombre'))
        if not title_elem:
            title_elem = item.find(class_=re.compile(r'card-title|asset-title'))
        if title_elem:
            listing['title'] = title_elem.get_text(strip=True)

        # Precio
        price_elem = item.find(class_=re.compile(r'price|precio'))
        if price_elem:
            listing['price'] = price_elem.get_text(strip=True)

        # Ubicación
        location_elem = item.find(class_=re.compile(r'location|ubicacion|direccion'))
        if location_elem:
            location_text = location_elem.get_text(strip=True)
            listing['city'] = location_text

        # Características
        features = item.find_all(class_=re.compile(r'feature|caracteristica|detail'))
        for feature in features:
            text = feature.get_text(strip=True).lower()

            if 'm²' in text or 'm2' in text or 'metro' in text:
                listing['surface'] = text
            elif 'hab' in text or 'dormitorio' in text:
                listing['bedrooms'] = text
            elif 'baño' in text:
                listing['bathrooms'] = text

        # Descripción
        desc_elem = item.find(class_=re.compile(r'description|descripcion'))
        if desc_elem:
            listing['description'] = desc_elem.get_text(strip=True)

        # Imagen
        img_elem = item.find('img')
        if img_elem:
            img_src = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-lazy')
            if img_src:
                listing['images'] = [img_src]

        return listing

    def parse_listing_detail(self, html: str, url: str) -> Dict[str, Any]:
        """Parsea la página de detalle."""
        return {}

    def get_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        """Extrae URL de la siguiente página."""
        soup = BeautifulSoup(html, 'html.parser')

        next_link = soup.find('a', class_=re.compile(r'next|siguiente|page-next'))

        if not next_link:
            pagination = soup.find(class_=re.compile(r'pagination|paginacion'))
            if pagination:
                current = pagination.find(class_=re.compile(r'active|current'))
                if current:
                    next_li = current.find_next_sibling()
                    if next_li:
                        next_link = next_li.find('a')

        if next_link and next_link.get('href'):
            return urljoin(self.base_url, next_link.get('href'))

        return None
