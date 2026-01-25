"""
Scraper para Pisos.com - Portal inmobiliario establecido desde 1996.
https://www.pisos.com
"""

import re
from typing import Any, Dict, List
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper


class PisosScraper(BaseScraper):
    """
    Scraper para Pisos.com

    Pisos.com es un portal inmobiliario español activo desde 1996,
    especialmente conocido por su amplia oferta de alquileres.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.base_url = 'https://www.pisos.com'

    def build_search_url(self, filters: Dict[str, Any]) -> str:
        """
        Construye URL de búsqueda de Pisos.com.

        Formato típico: /venta/pisos-{city}/
        Ejemplo: /venta/pisos-zaragoza/
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
            operation_path = 'venta'
        else:
            operation_path = 'alquiler'

        # Tipo de propiedad
        property_type = filters.get('property_type', 'piso')
        if property_type == 'piso':
            property_path = 'pisos'
        elif property_type == 'casa':
            property_path = 'casas'
        else:
            property_path = 'viviendas'

        # Construir URL base
        # Formato Pisos.com: /venta/pisos-{city}/
        if city:
            location_str = city
        elif province:
            location_str = province
        else:
            location_str = ""

        if location_str:
            url = f"{self.base_url}/{operation_path}/{property_path}-{location_str}/"
        else:
            url = f"{self.base_url}/{operation_path}/{property_path}/"

        # Agregar filtros como query params
        params = {}

        # Precio máximo
        price_max = filters.get('price', {}).get('max')
        if price_max:
            params['preciomax'] = price_max

        # Habitaciones mínimas
        bedrooms_min = filters.get('bedrooms', {}).get('min')
        if bedrooms_min:
            params['habitacionesmin'] = bedrooms_min

        # Superficie mínima
        surface_min = filters.get('surface', {}).get('min')
        if surface_min:
            params['superficiemin'] = surface_min

        if params:
            url += '?' + urlencode(params)

        self.logger.info(f"🔗 Pisos.com search URL: {url}")
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
        Parsea la página de listado de Pisos.com.
        """
        soup = BeautifulSoup(html, 'html.parser')
        listings = []

        # Buscar artículos/items de propiedades
        # Pisos.com puede usar diferentes estructuras
        items = soup.find_all('article', class_=re.compile(r'property|ad-preview|anuncio'))

        if not items:
            # Fallback: buscar divs con clases comunes
            items = soup.select('article, .property-card, .ad-preview, .anuncio, .listing-item')

        self.logger.debug(f"🔍 Pisos.com: Found {len(items)} items in HTML ({len(html)} bytes)")

        for item in items:
            try:
                listing = self._parse_listing_item(item)
                if listing.get('url'):
                    listings.append(listing)
            except Exception as e:
                self.logger.debug(f"Error parsing Pisos.com item: {e}")
                continue

        return listings

    def _parse_listing_item(self, item: BeautifulSoup) -> Dict[str, Any]:
        """Extrae datos de un item de Pisos.com."""
        listing = {}

        # URL - Buscar enlace principal
        link = item.find('a', class_=re.compile(r'ad-title|property-link|anuncio-link'))
        if not link:
            link = item.find('a', href=re.compile(r'/piso/|/vivienda/|/anuncio/'))
        if not link:
            # Fallback: primer enlace
            link = item.find('a')

        if link and link.get('href'):
            href = link.get('href')
            listing['url'] = urljoin(self.base_url, href)

        # Título
        title_elem = item.find(class_=re.compile(r'ad-title|property-title|titulo'))
        if not title_elem:
            title_elem = item.find(['h2', 'h3', 'h4'])

        if title_elem:
            listing['title'] = title_elem.get_text(strip=True)
        elif link:
            # Usar texto del link como título
            title_text = link.get_text(strip=True)
            if title_text:
                listing['title'] = title_text

        # Precio
        price_elem = item.find(class_=re.compile(r'ad-price|price|precio'))
        if not price_elem:
            price_elem = item.find('span', class_=re.compile(r'price|precio'))

        if price_elem:
            price_text = price_elem.get_text(strip=True)
            listing['price'] = price_text

        # Ubicación
        location_elem = item.find(class_=re.compile(r'location|ubicacion|zona'))
        if not location_elem:
            location_elem = item.find('span', class_=re.compile(r'location|ubicacion'))

        if location_elem:
            listing['city'] = location_elem.get_text(strip=True)

        # Características (superficie, habitaciones, baños)
        features = item.find_all(class_=re.compile(r'feature|caracteristica|detail'))

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

        # Si no encontramos features estructuradas, buscar en texto completo
        if not listing.get('surface') or not listing.get('bedrooms'):
            all_text = item.get_text()

            if not listing.get('surface'):
                surface_match = re.search(r'(\d+)\s*m[²2]', all_text)
                if surface_match:
                    listing['surface'] = f"{surface_match.group(1)} m²"

            if not listing.get('bedrooms'):
                bedrooms_match = re.search(r'(\d+)\s*hab', all_text, re.IGNORECASE)
                if bedrooms_match:
                    listing['bedrooms'] = f"{bedrooms_match.group(1)} hab"

            if not listing.get('bathrooms'):
                bathrooms_match = re.search(r'(\d+)\s*baño', all_text, re.IGNORECASE)
                if bathrooms_match:
                    listing['bathrooms'] = f"{bathrooms_match.group(1)} baño"

        # Descripción
        desc_elem = item.find(class_=re.compile(r'description|descripcion|desc'))
        if desc_elem:
            listing['description'] = desc_elem.get_text(strip=True)

        # Imágenes
        img_elem = item.find('img')
        if img_elem:
            img_src = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-lazy')
            if img_src:
                listing['images'] = [img_src]

        return listing

    def parse_listing_detail(self, html: str, url: str) -> Dict[str, Any]:
        """
        Parsea la página de detalle de un anuncio.
        """
        soup = BeautifulSoup(html, 'html.parser')
        details = {}

        # Implementar si se necesita

        return details

    def extract_next_page_url(self, html: str, current_url: str) -> str:
        """
        Extrae URL de la siguiente página.
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Buscar enlace "siguiente"
        next_link = soup.find('a', class_=re.compile(r'next|siguiente'))
        if not next_link:
            next_link = soup.find('a', rel='next')

        if not next_link:
            # Buscar en paginación
            pagination = soup.find(class_=re.compile(r'pagination|paginacion'))
            if pagination:
                links = pagination.find_all('a')
                for link in links:
                    link_text = link.get_text().lower()
                    if 'siguiente' in link_text or 'next' in link_text or '›' in link_text:
                        next_link = link
                        break

        if next_link and next_link.get('href'):
            next_url = urljoin(self.base_url, next_link.get('href'))
            return next_url

        return ""
