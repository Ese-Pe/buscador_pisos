"""
Scraper para Idealista.com - Portal líder inmobiliario en España.
https://www.idealista.com

Requires Selenium due to anti-bot protection (JavaScript rendering).
"""

import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from .base_scraper import SeleniumBaseScraper


class IdealistaScraper(SeleniumBaseScraper):
    """
    Scraper para Idealista.com using Selenium.

    Idealista es el portal inmobiliario líder en España con más de 50M de visitas
    mensuales y más de 1.2M de anuncios.

    Uses Selenium to bypass anti-bot protection and JavaScript rendering.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.base_url = 'https://www.idealista.com'
        self.name = 'idealista'

    def build_search_url(self, filters: Dict[str, Any]) -> str:
        """
        Construye URL de búsqueda de Idealista.

        Formato: /venta-viviendas/{city}-{province}/
        Ejemplo: /venta-viviendas/zaragoza-zaragoza/
        """
        location = filters.get('location', {})
        province = location.get('province', '').lower()
        city = location.get('city', '').lower()

        # Normalizar para URL (quitar acentos, espacios)
        province = self._normalize_for_url(province)
        city = self._normalize_for_url(city)

        # Tipo de operación
        operation = filters.get('operation_type', 'compra')
        if operation in ['compra', 'venta']:
            operation_path = 'venta-viviendas'
        else:
            operation_path = 'alquiler-viviendas'

        # Construir URL base
        if city and province:
            # Format: /venta-viviendas/city-province/
            url = f"{self.base_url}/{operation_path}/{city}-{province}/"
        elif province:
            # Format: /venta-viviendas/province-provincia/
            url = f"{self.base_url}/{operation_path}/{province}-provincia/"
        else:
            # Fallback a búsqueda general
            url = f"{self.base_url}/{operation_path}/"

        # Agregar filtros como query params si es necesario
        params = {}

        # Precio máximo
        price_max = filters.get('price', {}).get('max')
        if price_max:
            params['precioHasta'] = price_max

        # Habitaciones mínimas
        bedrooms_min = filters.get('bedrooms', {}).get('min')
        if bedrooms_min:
            params['habitaciones'] = bedrooms_min

        # Superficie mínima
        surface_min = filters.get('surface', {}).get('min')
        if surface_min:
            params['superficieMinima'] = surface_min

        if params:
            url += '?' + urlencode(params)

        self.logger.info(f"🔗 Idealista search URL: {url}")
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
        Parsea la página de listado de Idealista.

        Idealista usa estructura de artículos con clase 'item' o 'item-info-container'.
        """
        soup = BeautifulSoup(html, 'html.parser')
        listings = []

        # Buscar artículos de propiedades
        # Idealista usa <article> con clase "item" o contenedores similares
        items = soup.find_all('article', class_=re.compile(r'item'))

        if not items:
            # Fallback: buscar por otros selectores comunes
            items = soup.select('article, .item-info-container, .property-card')

        self.logger.debug(f"🔍 Idealista: Found {len(items)} items in HTML ({len(html)} bytes)")

        for item in items:
            try:
                listing = self._parse_listing_item(item)
                if listing.get('url'):
                    listings.append(listing)
            except Exception as e:
                self.logger.debug(f"Error parsing Idealista item: {e}")
                continue

        return listings

    def _parse_listing_item(self, item: BeautifulSoup) -> Dict[str, Any]:
        """Extrae datos de un item de Idealista."""
        listing = {}

        # URL - Buscar enlace principal
        link = item.find('a', class_=re.compile(r'item-link|property-link'))
        if not link:
            link = item.find('a', href=re.compile(r'/inmueble/'))

        if link and link.get('href'):
            href = link.get('href')
            listing['url'] = urljoin(self.base_url, href)

            # Título desde el link si tiene texto
            if not listing.get('title'):
                title = link.get_text(strip=True)
                if title:
                    listing['title'] = title

        # Título - Buscar en varios lugares
        if not listing.get('title'):
            title_elem = item.find('a', class_=re.compile(r'item-link'))
            if not title_elem:
                title_elem = item.find(['h2', 'h3'], class_=re.compile(r'item-title|property-title'))
            if not title_elem:
                title_elem = item.find(['h2', 'h3'])

            if title_elem:
                listing['title'] = title_elem.get_text(strip=True)

        # Precio
        price_elem = item.find(class_=re.compile(r'item-price|price-row|precio'))
        if not price_elem:
            price_elem = item.find('span', class_='price')

        if price_elem:
            price_text = price_elem.get_text(strip=True)
            listing['price'] = price_text

        # Ubicación/Localidad
        location_elem = item.find(class_=re.compile(r'item-location|item-detail-char|ubicacion'))
        if not location_elem:
            location_elem = item.find('span', class_='item-detail')

        if location_elem:
            location_text = location_elem.get_text(strip=True)
            listing['city'] = location_text

        # Características (superficie, habitaciones, baños)
        details = item.find_all(class_=re.compile(r'item-detail|item-detail-char'))
        for detail in details:
            text = detail.get_text(strip=True).lower()

            # Superficie (m²)
            if 'm²' in text or 'm2' in text:
                listing['surface'] = text

            # Habitaciones
            elif 'hab' in text or 'habitacion' in text:
                listing['bedrooms'] = text

            # Baños
            elif 'baño' in text or 'bath' in text:
                listing['bathrooms'] = text

        # Descripción
        desc_elem = item.find(class_=re.compile(r'item-description|description|descripcion'))
        if desc_elem:
            listing['description'] = desc_elem.get_text(strip=True)

        # Imágenes
        img_elem = item.find('img')
        if img_elem:
            img_src = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-ondemand-img')
            if img_src:
                listing['images'] = [img_src]

        return listing

    def parse_listing_detail(self, html: str, url: str) -> Dict[str, Any]:
        """
        Parsea la página de detalle de un anuncio.

        Opcional - podemos agregar más detalles si se necesita.
        """
        soup = BeautifulSoup(html, 'html.parser')
        details = {}

        # Por ahora retornamos dict vacío
        # Se puede implementar extracción detallada si se necesita

        return details

    def get_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        """
        Extrae URL de la siguiente página de resultados.

        Idealista usa paginación con números de página.
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Buscar enlace "siguiente" o "next"
        next_link = soup.find('a', class_=re.compile(r'next|siguiente'))

        if not next_link:
            # Buscar en paginación numérica
            pagination = soup.find('div', class_=re.compile(r'pagination'))
            if pagination:
                links = pagination.find_all('a')
                # El último link suele ser "siguiente"
                if links:
                    next_link = links[-1]

        if next_link and next_link.get('href'):
            next_url = urljoin(self.base_url, next_link.get('href'))
            return next_url

        return None
