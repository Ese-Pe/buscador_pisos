"""
Scraper para Habitaclia.com - Portal inmobiliario popular en España.
https://www.habitaclia.com

Requires Selenium due to JavaScript rendering and anti-bot protection.
"""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from .base_scraper import SeleniumBaseScraper


class HabitacliaScraper(SeleniumBaseScraper):
    """
    Scraper para Habitaclia.com using Selenium.

    Habitaclia es un portal inmobiliario muy popular especialmente en
    Cataluña y otras regiones de España.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.base_url = 'https://www.habitaclia.com'
        self.name = 'habitaclia'

    def build_search_url(self, filters: Dict[str, Any]) -> str:
        """
        Construye URL de búsqueda de Habitaclia.

        Formato: /viviendas-{city}.htm
        Ejemplo: /viviendas-zaragoza.htm
        """
        location = filters.get('location', {})
        province = location.get('province', '').lower()
        city = location.get('city', '').lower()

        # Normalizar para URL
        province = self._normalize_for_url(province)
        city = self._normalize_for_url(city)

        # Construir URL base - Habitaclia uses simple format: /viviendas-{location}.htm
        if city:
            url = f"{self.base_url}/viviendas-{city}.htm"
        elif province:
            url = f"{self.base_url}/viviendas-{province}.htm"
        else:
            url = f"{self.base_url}/viviendas.htm"

        # Agregar filtros como query params
        params = {}

        price_max = filters.get('price', {}).get('max')
        if price_max:
            params['precio_max'] = price_max

        bedrooms_min = filters.get('bedrooms', {}).get('min')
        if bedrooms_min:
            params['habitaciones_min'] = bedrooms_min

        surface_min = filters.get('surface', {}).get('min')
        if surface_min:
            params['metros_min'] = surface_min

        if params:
            url += '?' + urlencode(params)

        self.logger.info(f"Habitaclia search URL: {url}")
        return url

    def _normalize_for_url(self, text: str) -> str:
        """Normaliza texto para URL."""
        if not text:
            return ''

        text = text.lower().strip()

        # Reemplazar acentos
        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'ñ': 'n', 'ü': 'u', 'à': 'a', 'è': 'e', 'ì': 'i',
            'ò': 'o', 'ù': 'u', 'ç': 'c'
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        # Reemplazar espacios con guiones
        text = text.replace(' ', '-')

        return text

    def parse_listing_list(self, html: str) -> List[Dict[str, Any]]:
        """
        Parsea la página de listado de Habitaclia.

        Habitaclia uses:
        - .list-item for each property card
        - .list-item-title for title/link
        - .list-item-price for price
        - .list-item-location for location
        - .list-item-feature for features
        """
        soup = BeautifulSoup(html, 'html.parser')
        listings = []

        # Habitaclia uses class 'list-item' for property cards
        items = soup.find_all(class_='list-item')

        if not items:
            # Fallback: try article elements or other containers
            items = soup.find_all('article')

        self.logger.debug(f"Habitaclia: Found {len(items)} items in HTML ({len(html)} bytes)")

        for item in items:
            try:
                listing = self._parse_listing_item(item)
                if listing.get('url'):
                    listings.append(listing)
            except Exception as e:
                self.logger.debug(f"Error parsing Habitaclia item: {e}")
                continue

        return listings

    def _parse_listing_item(self, item: BeautifulSoup) -> Dict[str, Any]:
        """Extrae datos de un item de Habitaclia."""
        listing = {}

        # URL and Title - from list-item-title link
        title_link = item.find('a', class_='list-item-title')
        if title_link:
            if title_link.get('href'):
                listing['url'] = urljoin(self.base_url, title_link.get('href'))
            listing['title'] = title_link.get_text(strip=True)

        # Fallback URL search
        if not listing.get('url'):
            link = item.find('a', href=re.compile(r'/vivienda|/piso|/casa|/inmueble'))
            if link and link.get('href'):
                listing['url'] = urljoin(self.base_url, link.get('href'))

        # Precio - from list-item-price
        price_elem = item.find(class_='list-item-price')
        if price_elem:
            listing['price'] = price_elem.get_text(strip=True)

        # Ubicación - from list-item-location
        location_elem = item.find(class_='list-item-location')
        if location_elem:
            listing['city'] = location_elem.get_text(strip=True)

        # Características - from list-item-feature elements
        features = item.find_all(class_='list-item-feature')
        for feature in features:
            text = feature.get_text(strip=True).lower()

            if 'm²' in text or 'm2' in text:
                listing['surface'] = text
            elif 'hab' in text or 'habitacion' in text or 'dorm' in text:
                listing['bedrooms'] = text
            elif 'baño' in text:
                listing['bathrooms'] = text

        # Descripción - from list-item-description
        desc_elem = item.find(class_='list-item-description')
        if desc_elem:
            listing['description'] = desc_elem.get_text(strip=True)

        # Imagen
        img_elem = item.find('img')
        if img_elem:
            img_src = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-lazy')
            if img_src and not img_src.startswith('data:'):
                listing['images'] = [img_src]

        return listing

    def parse_listing_detail(self, html: str, url: str) -> Dict[str, Any]:
        """Parsea la página de detalle de un anuncio."""
        return {}

    def get_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        """Extrae URL de la siguiente página."""
        soup = BeautifulSoup(html, 'html.parser')

        # Buscar enlace siguiente
        next_link = soup.find('a', class_=re.compile(r'next|siguiente'))

        if not next_link:
            pagination = soup.find('nav', class_=re.compile(r'pagination'))
            if pagination:
                next_link = pagination.find('a', rel='next')

        if next_link and next_link.get('href'):
            return urljoin(self.base_url, next_link.get('href'))

        return None
