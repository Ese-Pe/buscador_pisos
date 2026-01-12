"""
Scraper para el portal Yaencontre.com
Portal agregador con carga dinámica JavaScript.
"""

import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from .base_scraper import SeleniumBaseScraper


class YaencontreScraper(SeleniumBaseScraper):
    """
    Scraper para yaencontre.com
    
    Requiere Selenium debido a la carga dinámica de contenido.
    """
    
    name = "yaencontre"
    base_url = "https://www.yaencontre.com"
    requires_selenium = True
    
    PROPERTY_TYPES = {
        'piso': 'pisos',
        'casa': 'casas',
        'atico': 'aticos',
        'duplex': 'duplex',
        'estudio': 'estudios',
    }
    
    def build_search_url(self, filters: Dict[str, Any]) -> str:
        operation = 'venta' if filters.get('operation_type') == 'compra' else 'alquiler'
        prop_type = self.PROPERTY_TYPES.get(filters.get('property_type', 'piso'), 'pisos')
        
        location = filters.get('location', {})
        province = location.get('province', '').lower().replace(' ', '-')
        city = location.get('city', '').lower().replace(' ', '-')
        
        # Construir path
        if city and province:
            path = f"/{prop_type}/{operation}/{province}/{city}"
        elif province:
            path = f"/{prop_type}/{operation}/{province}"
        else:
            path = f"/{prop_type}/{operation}"
        
        # Parámetros
        params = {}
        if filters.get('price', {}).get('min'):
            params['precioMin'] = filters['price']['min']
        if filters.get('price', {}).get('max'):
            params['precioMax'] = filters['price']['max']
        if filters.get('surface', {}).get('min'):
            params['superficieMin'] = filters['surface']['min']
        if filters.get('bedrooms', {}).get('min'):
            params['habitaciones'] = filters['bedrooms']['min']
        
        url = self.base_url + path
        if params:
            url += '?' + urlencode(params)
        return url
    
    def parse_listing_list(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        listings = []
        
        # Yaencontre usa diferentes estructuras
        items = soup.select('.property-card, .listing-card, article[data-id], .result-item')
        
        for item in items:
            try:
                listing = {}
                
                # URL
                link = item.select_one('a[href*="/inmueble/"], a[href*="/vivienda/"], a.property-link')
                if link:
                    listing['url'] = urljoin(self.base_url, link.get('href', ''))
                    listing['title'] = link.get('title', '') or link.get_text(strip=True)
                
                # ID del portal
                listing['portal_id'] = item.get('data-id') or item.get('data-listing-id')
                
                # Precio
                price = item.select_one('.price, .property-price, span[data-price]')
                if price:
                    listing['price'] = price.get('data-price') or price.get_text(strip=True)
                
                # Ubicación
                location = item.select_one('.location, .property-location, .address')
                if location:
                    loc_text = location.get_text(strip=True)
                    # Intentar separar ciudad y zona
                    parts = [p.strip() for p in loc_text.split(',')]
                    if len(parts) >= 2:
                        listing['zone'] = parts[0]
                        listing['city'] = parts[1]
                    else:
                        listing['city'] = loc_text
                
                # Características
                features = item.select('.feature, .property-feature, .specs span')
                for feat in features:
                    text = feat.get_text(strip=True).lower()
                    if 'hab' in text:
                        listing['bedrooms'] = re.search(r'(\d+)', text).group(1) if re.search(r'(\d+)', text) else None
                    elif 'baño' in text:
                        listing['bathrooms'] = re.search(r'(\d+)', text).group(1) if re.search(r'(\d+)', text) else None
                    elif 'm²' in text or 'm2' in text:
                        listing['surface'] = re.search(r'(\d+)', text).group(1) if re.search(r'(\d+)', text) else None
                
                # Imagen
                img = item.select_one('img[src], img[data-src], img[data-lazy]')
                if img:
                    img_url = img.get('src') or img.get('data-src') or img.get('data-lazy')
                    if img_url and not img_url.startswith('data:'):
                        listing['images'] = [urljoin(self.base_url, img_url)]
                
                if listing.get('url'):
                    listings.append(listing)
                    
            except Exception as e:
                self.logger.debug(f"Error parseando item: {e}")
        
        return listings
    
    def parse_listing_detail(self, html: str, url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, 'html.parser')
        data = {'url': url}
        
        # Título
        title = soup.select_one('h1, .property-title, .listing-title')
        if title:
            data['title'] = title.get_text(strip=True)
        
        # Precio
        price = soup.select_one('.price, .property-price, [itemprop="price"]')
        if price:
            data['price'] = price.get('content') or price.get_text(strip=True)
        
        # Descripción
        desc = soup.select_one('.description, .property-description, [itemprop="description"]')
        if desc:
            data['description'] = desc.get_text(strip=True)[:2000]
        
        # Ubicación
        address = soup.select_one('.address, .property-address, [itemprop="address"]')
        if address:
            data['address'] = address.get_text(strip=True)
        
        # Características principales
        main_features = soup.select('.main-features li, .property-highlights span, .specs-main span')
        for feat in main_features:
            text = feat.get_text(strip=True).lower()
            if 'habitacion' in text or 'dormitorio' in text:
                match = re.search(r'(\d+)', text)
                if match:
                    data['bedrooms'] = match.group(1)
            elif 'baño' in text:
                match = re.search(r'(\d+)', text)
                if match:
                    data['bathrooms'] = match.group(1)
            elif 'm²' in text or 'superficie' in text:
                match = re.search(r'(\d+)', text)
                if match:
                    data['surface'] = match.group(1)
        
        # Características adicionales
        extra_features = soup.select('.features li, .extras li, .amenities li, .property-features li')
        for feat in extra_features:
            text = feat.get_text(strip=True).lower()
            if 'ascensor' in text:
                data['has_elevator'] = True
            elif 'garaje' in text or 'parking' in text:
                data['has_parking'] = True
            elif 'piscina' in text:
                data['has_pool'] = True
            elif 'trastero' in text:
                data['has_storage'] = True
            elif 'terraza' in text:
                data['has_terrace'] = True
            elif 'aire acondicionado' in text or 'a/a' in text:
                data['has_ac'] = True
            elif 'calefaccion' in text:
                data['has_heating'] = True
            elif 'exterior' in text:
                data['is_exterior'] = True
            elif 'planta' in text:
                data['floor'] = text
        
        # Imágenes
        images = soup.select('.gallery img, .photos img, .slider img, [itemprop="image"]')
        data['images'] = []
        for img in images[:15]:
            img_url = img.get('src') or img.get('data-src') or img.get('content')
            if img_url and not img_url.startswith('data:'):
                data['images'].append(urljoin(self.base_url, img_url))
        
        # Agencia
        agency = soup.select_one('.advertiser, .agency, .contact-name')
        if agency:
            data['agency'] = agency.get_text(strip=True)
        
        # Teléfono
        phone = soup.select_one('.phone, [href^="tel:"]')
        if phone:
            data['contact_phone'] = phone.get('href', '').replace('tel:', '') or phone.get_text(strip=True)
        
        return data
    
    def get_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Buscar botón/link siguiente
        next_link = soup.select_one('a.next, a[rel="next"], .pagination .next a, button.load-more')
        if next_link and next_link.get('href'):
            return urljoin(self.base_url, next_link['href'])
        
        # Verificar si hay más páginas por número
        pagination = soup.select('.pagination a, .pager a')
        if pagination:
            # Buscar el número de página actual y siguiente
            current_page = 1
            for link in pagination:
                if 'active' in link.get('class', []) or 'current' in link.get('class', []):
                    try:
                        current_page = int(link.get_text(strip=True))
                    except ValueError:
                        pass
            
            # Buscar link a página siguiente
            for link in pagination:
                try:
                    page_num = int(link.get_text(strip=True))
                    if page_num == current_page + 1:
                        return urljoin(self.base_url, link.get('href', ''))
                except ValueError:
                    continue
        
        return None
    
    def _fetch_page(self, url: str) -> Optional[str]:
        """Sobrescribe para manejar scroll dinámico."""
        html = super()._fetch_page(url)
        
        if html and self._driver:
            # Scroll para cargar contenido lazy
            try:
                for _ in range(3):
                    self._driver.execute_script("window.scrollBy(0, 500);")
                    time.sleep(0.5)
                # Volver arriba
                self._driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
                html = self._driver.page_source
            except Exception as e:
                self.logger.debug(f"Error en scroll: {e}")
        
        return html
