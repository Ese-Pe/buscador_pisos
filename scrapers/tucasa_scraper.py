"""
Scraper para el portal Tucasa.com
Agregador de anuncios inmobiliarios en España.
"""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper


class TucasaScraper(BaseScraper):
    """Scraper para tucasa.com"""
    
    name = "tucasa"
    base_url = "https://www.tucasa.com"
    
    PROPERTY_TYPES = {
        'piso': 'pisos', 'casa': 'casas', 'atico': 'aticos',
        'duplex': 'duplex', 'estudio': 'estudios', 'chalet': 'chalets',
    }
    
    def build_search_url(self, filters: Dict[str, Any]) -> str:
        operation = 'comprar' if filters.get('operation_type') == 'compra' else 'alquilar'
        property_type = self.PROPERTY_TYPES.get(filters.get('property_type', 'piso'), 'pisos')
        
        location = filters.get('location', {})
        city = location.get('city', '').lower().replace(' ', '-').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
        province = location.get('province', '').lower().replace(' ', '-')
        
        if city and province:
            path = f"/{operation}/{property_type}/{province}/{city}"
        elif province:
            path = f"/{operation}/{property_type}/{province}"
        else:
            path = f"/{operation}/{property_type}"
        
        params = {}
        if filters.get('price', {}).get('min'):
            params['preciomin'] = filters['price']['min']
        if filters.get('price', {}).get('max'):
            params['preciomax'] = filters['price']['max']
        if filters.get('surface', {}).get('min'):
            params['metrosmin'] = filters['surface']['min']
        if filters.get('bedrooms', {}).get('min'):
            params['habitacionesmin'] = filters['bedrooms']['min']
        
        url = self.base_url + path
        if params:
            url += '?' + urlencode(params)
        return url
    
    def parse_listing_list(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        listings = []
        
        # Buscar artículos de propiedades
        items = soup.select('article, div.property-card, div.listing-item, li.property-item')
        
        for item in items:
            try:
                listing = {}
                
                # URL y título
                link = item.select_one('a[href*="/inmueble/"], a[href*="/property/"], h2 a, h3 a')
                if link:
                    listing['url'] = urljoin(self.base_url, link.get('href', ''))
                    listing['title'] = link.get_text(strip=True)
                
                # Precio
                price_el = item.select_one('.price, .property-price, [class*="price"]')
                if price_el:
                    listing['price'] = price_el.get_text(strip=True)
                
                # Ubicación
                location_el = item.select_one('.location, .property-location, [class*="location"], address')
                if location_el:
                    loc_text = location_el.get_text(strip=True)
                    listing['city'] = loc_text
                
                # Características
                features = item.select('.feature, .property-feature, span[class*="room"], span[class*="bath"], span[class*="m2"]')
                for feat in features:
                    text = feat.get_text(strip=True).lower()
                    if 'hab' in text or 'dorm' in text:
                        listing['bedrooms'] = text
                    elif 'baño' in text:
                        listing['bathrooms'] = text
                    elif 'm²' in text or 'm2' in text:
                        listing['surface'] = text
                
                # Imagen
                img = item.select_one('img[src], img[data-src]')
                if img:
                    img_url = img.get('src') or img.get('data-src')
                    if img_url:
                        listing['images'] = [urljoin(self.base_url, img_url)]
                
                if listing.get('url'):
                    listings.append(listing)
                    
            except Exception as e:
                self.logger.debug(f"Error parseando item: {e}")
                continue
        
        return listings
    
    def parse_listing_detail(self, html: str, url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, 'html.parser')
        data = {'url': url}
        
        # Título
        title = soup.select_one('h1, .property-title, .listing-title')
        if title:
            data['title'] = title.get_text(strip=True)
        
        # Precio
        price = soup.select_one('.price, .property-price, [class*="precio"]')
        if price:
            data['price'] = price.get_text(strip=True)
        
        # Descripción
        desc = soup.select_one('.description, .property-description, [class*="descripcion"]')
        if desc:
            data['description'] = desc.get_text(strip=True)[:2000]
        
        # Características principales
        features = soup.select('[class*="feature"], [class*="caracteristica"], .property-details li')
        for feat in features:
            text = feat.get_text(strip=True).lower()
            if 'habitacion' in text or 'dormitorio' in text:
                data['bedrooms'] = text
            elif 'baño' in text:
                data['bathrooms'] = text
            elif 'm²' in text or 'metro' in text:
                data['surface'] = text
            elif 'planta' in text or 'piso' in text:
                data['floor'] = text
            elif 'ascensor' in text:
                data['has_elevator'] = 'sin' not in text and 'no' not in text
            elif 'garaje' in text or 'parking' in text:
                data['has_parking'] = 'sin' not in text and 'no' not in text
            elif 'piscina' in text:
                data['has_pool'] = 'sin' not in text and 'no' not in text
            elif 'trastero' in text:
                data['has_storage'] = 'sin' not in text and 'no' not in text
            elif 'terraza' in text:
                data['has_terrace'] = 'sin' not in text and 'no' not in text
            elif 'aire' in text:
                data['has_ac'] = 'sin' not in text and 'no' not in text
        
        # Imágenes
        images = soup.select('img[src*="property"], img[src*="inmueble"], .gallery img')
        data['images'] = [urljoin(self.base_url, img.get('src')) for img in images[:10] if img.get('src')]
        
        # Ubicación
        address = soup.select_one('.address, .location, [class*="direccion"], [class*="ubicacion"]')
        if address:
            data['address'] = address.get_text(strip=True)
        
        # Agencia
        agency = soup.select_one('.agency, .advertiser, [class*="inmobiliaria"]')
        if agency:
            data['agency'] = agency.get_text(strip=True)
        
        return data
    
    def get_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Buscar link a siguiente página
        next_link = soup.select_one('a.next, a[rel="next"], .pagination a:contains("Siguiente"), .pagination .next a')
        if next_link and next_link.get('href'):
            return urljoin(self.base_url, next_link['href'])
        
        # Buscar por patrón de paginación en URL
        parsed = urlparse(current_url)
        params = parse_qs(parsed.query)
        
        current_page = int(params.get('page', [1])[0])
        
        # Verificar si hay más páginas (buscar indicadores)
        pagination = soup.select('.pagination a, .pager a')
        if pagination:
            params['page'] = [str(current_page + 1)]
            new_query = urlencode({k: v[0] for k, v in params.items()})
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"
        
        return None
