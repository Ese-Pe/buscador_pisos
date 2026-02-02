"""
Scraper para Fotocasa.es - Portal inmobiliario con 13M+ visitas mensuales.
https://www.fotocasa.es

Requires Selenium due to anti-bot protection (JavaScript rendering).
"""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from .base_scraper import SeleniumBaseScraper


class FotocasaScraper(SeleniumBaseScraper):
    """
    Scraper para Fotocasa.es using Selenium.

    Fotocasa es uno de los principales portales inmobiliarios en España
    con más de 13 millones de visitas mensuales.

    Uses Selenium to bypass anti-bot protection and JavaScript rendering.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.base_url = 'https://www.fotocasa.es'
        self.name = 'fotocasa'

    def build_search_url(self, filters: Dict[str, Any]) -> str:
        """
        Construye URL de búsqueda de Fotocasa.

        Formato: /es/comprar/viviendas/{location}/todas-las-zonas/l
        Ejemplo: /es/comprar/viviendas/zaragoza-capital/todas-las-zonas/l
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
            operation_path = 'alquiler'

        # Tipo de propiedad
        property_type = filters.get('property_type', 'piso')
        if property_type == 'piso':
            property_path = 'viviendas'  # o 'pisos'
        else:
            property_path = 'viviendas'

        # Construir URL base
        # Formato Fotocasa: /es/comprar/viviendas/{city}-capital/todas-las-zonas/l
        if city:
            location_path = f"{city}-capital"
        elif province:
            location_path = f"{province}-provincia"
        else:
            location_path = "espana"

        url = f"{self.base_url}/es/{operation_path}/{property_path}/{location_path}/todas-las-zonas/l"

        # Agregar filtros como query params
        params = {}

        # Precio máximo
        price_max = filters.get('price', {}).get('max')
        if price_max:
            params['maxPrice'] = price_max

        # Habitaciones mínimas
        bedrooms_min = filters.get('bedrooms', {}).get('min')
        if bedrooms_min:
            params['minRooms'] = bedrooms_min

        # Superficie mínima
        surface_min = filters.get('surface', {}).get('min')
        if surface_min:
            params['minSurface'] = surface_min

        if params:
            url += '?' + urlencode(params)

        self.logger.info(f"🔗 Fotocasa search URL: {url}")
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
        Parsea la página de listado de Fotocasa.

        Fotocasa usa estructura de artículos con clases específicas.
        """
        soup = BeautifulSoup(html, 'html.parser')
        listings = []

        # Buscar artículos de propiedades
        # Fotocasa usa diferentes clases según el layout
        items = soup.find_all('article', class_=re.compile(r're-Card|PropertyCard'))

        if not items:
            # Fallback: buscar por otros selectores
            items = soup.select('article, .property-card, .re-Card')

        self.logger.debug(f"🔍 Fotocasa: Found {len(items)} items in HTML ({len(html)} bytes)")

        for item in items:
            try:
                listing = self._parse_listing_item(item)
                if listing.get('url'):
                    listings.append(listing)
            except Exception as e:
                self.logger.debug(f"Error parsing Fotocasa item: {e}")
                continue

        return listings

    def _parse_listing_item(self, item: BeautifulSoup) -> Dict[str, Any]:
        """Extrae datos de un item de Fotocasa."""
        listing = {}

        # URL - Buscar enlace principal
        link = item.find('a', class_=re.compile(r're-Card-link|property-link'))
        if not link:
            link = item.find('a', href=re.compile(r'/inmueble/|/vivienda/'))
        if not link:
            # Fallback: cualquier enlace
            link = item.find('a')

        if link and link.get('href'):
            href = link.get('href')
            listing['url'] = urljoin(self.base_url, href)

        # Título
        title_elem = item.find(class_=re.compile(r're-Card-title|property-title'))
        if not title_elem:
            title_elem = item.find(['h2', 'h3', 'h4'])

        if title_elem:
            listing['title'] = title_elem.get_text(strip=True)

        # Precio
        price_elem = item.find(class_=re.compile(r're-Card-price|price|precio'))
        if not price_elem:
            price_elem = item.find('span', class_=re.compile(r'price'))

        if price_elem:
            price_text = price_elem.get_text(strip=True)
            listing['price'] = price_text

        # Ubicación
        location_elem = item.find(class_=re.compile(r're-Card-location|location|ubicacion'))
        if not location_elem:
            location_elem = item.find('span', class_=re.compile(r'location'))

        if location_elem:
            listing['city'] = location_elem.get_text(strip=True)

        # Características (superficie, habitaciones, baños)
        features = item.find_all(class_=re.compile(r're-Card-features|features|caracteristicas'))
        for feature in features:
            text = feature.get_text(strip=True).lower()

            # Superficie
            if 'm²' in text or 'm2' in text:
                listing['surface'] = text

            # Habitaciones
            elif 'hab' in text or 'dorm' in text or 'room' in text:
                listing['bedrooms'] = text

            # Baños
            elif 'baño' in text or 'bath' in text:
                listing['bathrooms'] = text

        # Si no encontramos features, buscar en cualquier span/div
        if not listing.get('surface'):
            all_text = item.get_text()
            # Buscar patrón de m²
            surface_match = re.search(r'(\d+)\s*m[²2]', all_text)
            if surface_match:
                listing['surface'] = f"{surface_match.group(1)} m²"

        if not listing.get('bedrooms'):
            # Buscar patrón de habitaciones
            bedrooms_match = re.search(r'(\d+)\s*hab', all_text, re.IGNORECASE)
            if bedrooms_match:
                listing['bedrooms'] = f"{bedrooms_match.group(1)} hab"

        # Descripción
        desc_elem = item.find(class_=re.compile(r'description|descripcion'))
        if desc_elem:
            listing['description'] = desc_elem.get_text(strip=True)

        # Imágenes
        img_elem = item.find('img')
        if img_elem:
            img_src = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-lazy-src')
            if img_src:
                listing['images'] = [img_src]

        return listing

    def parse_listing_detail(self, html: str, url: str) -> Dict[str, Any]:
        """
        Parsea la página de detalle de un anuncio.
        """
        soup = BeautifulSoup(html, 'html.parser')
        details = {}

        # Implementar si se necesita extracción detallada

        return details

    def get_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        """
        Extrae URL de la siguiente página.

        Fotocasa usa paginación con parámetros de página.
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Buscar enlace "siguiente"
        next_link = soup.find('a', class_=re.compile(r'next|siguiente'))

        if not next_link:
            # Buscar en paginación
            pagination = soup.find(class_=re.compile(r'pagination|paginacion'))
            if pagination:
                links = pagination.find_all('a')
                # Buscar el link que tiene "siguiente" o un número mayor
                for link in links:
                    if 'next' in link.get('class', []) or 'siguiente' in link.get_text().lower():
                        next_link = link
                        break

        if next_link and next_link.get('href'):
            next_url = urljoin(self.base_url, next_link.get('href'))
            return next_url

        return None
