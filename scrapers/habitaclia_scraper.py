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

        Formato: /comprar-vivienda-en-{city}.htm
        Ejemplo: /comprar-vivienda-en-zaragoza.htm
        """
        location = filters.get('location', {})
        province = location.get('province', '').lower()
        city = location.get('city', '').lower()

        # Normalizar para URL
        province = self._normalize_for_url(province)
        city = self._normalize_for_url(city)

        # Tipo de operación
        operation = filters.get('operation_type', 'compra')
        if operation in ['compra', 'venta']:
            operation_path = 'comprar'
        else:
            operation_path = 'alquilar'

        # Construir URL base
        if city:
            url = f"{self.base_url}/{operation_path}-vivienda-en-{city}.htm"
        elif province:
            url = f"{self.base_url}/{operation_path}-vivienda-en-{province}_provincia.htm"
        else:
            url = f"{self.base_url}/{operation_path}-vivienda.htm"

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
        """
        soup = BeautifulSoup(html, 'html.parser')
        listings = []

        # Habitaclia usa artículos con clase 'list-item' o contenedores de anuncios
        items = soup.find_all('article', class_=re.compile(r'list-item|property-item'))

        if not items:
            # Fallback: buscar por selectores alternativos
            items = soup.select('.list-item, .property-card, [data-listid]')

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

        # URL - Buscar enlace principal
        link = item.find('a', class_=re.compile(r'list-item-link|property-link'))
        if not link:
            link = item.find('a', href=re.compile(r'/vivienda|/piso|/casa'))

        if link and link.get('href'):
            href = link.get('href')
            listing['url'] = urljoin(self.base_url, href)

        # Título
        title_elem = item.find(['h2', 'h3'], class_=re.compile(r'list-item-title|title'))
        if not title_elem:
            title_elem = item.find('a', class_=re.compile(r'list-item-link'))
        if title_elem:
            listing['title'] = title_elem.get_text(strip=True)

        # Precio
        price_elem = item.find(class_=re.compile(r'list-item-price|price'))
        if price_elem:
            listing['price'] = price_elem.get_text(strip=True)

        # Ubicación
        location_elem = item.find(class_=re.compile(r'list-item-location|location'))
        if location_elem:
            listing['city'] = location_elem.get_text(strip=True)

        # Características
        details = item.find_all(class_=re.compile(r'list-item-feature|feature'))
        for detail in details:
            text = detail.get_text(strip=True).lower()

            if 'm²' in text or 'm2' in text:
                listing['surface'] = text
            elif 'hab' in text or 'habitacion' in text or 'dorm' in text:
                listing['bedrooms'] = text
            elif 'baño' in text:
                listing['bathrooms'] = text

        # Descripción
        desc_elem = item.find(class_=re.compile(r'list-item-description|description'))
        if desc_elem:
            listing['description'] = desc_elem.get_text(strip=True)

        # Imagen
        img_elem = item.find('img')
        if img_elem:
            img_src = img_elem.get('src') or img_elem.get('data-src')
            if img_src:
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
