"""
Scraper para el portal Bienici.com
Portal inmobiliario con API JSON.
"""

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper


class BieniciScraper(BaseScraper):
    """
    Scraper para bienici.com
    
    Bienici es un portal francés con presencia en España.
    Tiene una API JSON que facilita la extracción de datos.
    """
    
    name = "bienici"
    base_url = "https://www.bienici.com"
    api_url = "https://www.bienici.com/realEstateAds.json"
    
    def build_search_url(self, filters: Dict[str, Any]) -> str:
        """Construye la URL de búsqueda para Bienici."""
        location = filters.get('location', {})
        city = location.get('city', '').lower()
        province = location.get('province', '').lower()
        
        # Bienici usa códigos de zona, construimos una URL de búsqueda
        operation = 'acheter' if filters.get('operation_type') == 'compra' else 'louer'
        
        # URL base de búsqueda
        if city:
            search_location = city.replace(' ', '-')
        elif province:
            search_location = province.replace(' ', '-')
        else:
            search_location = 'espagne'
        
        path = f"/{operation}/appartement/{search_location}"
        
        params = {}
        if filters.get('price', {}).get('min'):
            params['prix-min'] = filters['price']['min']
        if filters.get('price', {}).get('max'):
            params['prix-max'] = filters['price']['max']
        if filters.get('surface', {}).get('min'):
            params['surface-min'] = filters['surface']['min']
        if filters.get('bedrooms', {}).get('min'):
            params['nb-pieces-min'] = filters['bedrooms']['min']
        
        url = self.base_url + path
        if params:
            url += '?' + urlencode(params)
        return url
    
    def parse_listing_list(self, html: str) -> List[Dict[str, Any]]:
        """Parsea la página de listado de Bienici."""
        soup = BeautifulSoup(html, 'html.parser')
        listings = []
        
        # Intentar extraer datos JSON embebidos
        script_data = soup.find('script', {'id': '__NEXT_DATA__'})
        if script_data:
            try:
                data = json.loads(script_data.string)
                ads = self._extract_from_json(data)
                if ads:
                    return ads
            except json.JSONDecodeError:
                pass
        
        # Fallback a parsing HTML
        items = soup.select('.searchResults__item, .ad-overview, article.ad-card')
        
        for item in items:
            try:
                listing = {}
                
                # URL
                link = item.select_one('a[href*="/annonce/"], a[href*="/ad/"]')
                if link:
                    listing['url'] = urljoin(self.base_url, link.get('href', ''))
                
                # ID del portal
                listing['portal_id'] = item.get('data-id') or item.get('data-ad-id')
                
                # Título
                title = item.select_one('.ad-overview__title, h2, .title')
                if title:
                    listing['title'] = title.get_text(strip=True)
                
                # Precio
                price = item.select_one('.ad-price, .price, [data-price]')
                if price:
                    listing['price'] = price.get('data-price') or price.get_text(strip=True)
                
                # Ubicación
                location = item.select_one('.ad-overview__city, .location')
                if location:
                    listing['city'] = location.get_text(strip=True)
                
                # Características
                features = item.select('.ad-overview__infos span, .features span')
                for feat in features:
                    text = feat.get_text(strip=True).lower()
                    if 'pièce' in text or 'piece' in text or 'hab' in text:
                        match = re.search(r'(\d+)', text)
                        if match:
                            listing['bedrooms'] = match.group(1)
                    elif 'm²' in text:
                        match = re.search(r'(\d+)', text)
                        if match:
                            listing['surface'] = match.group(1)
                
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
        
        return listings
    
    def _extract_from_json(self, data: Dict) -> List[Dict[str, Any]]:
        """Extrae anuncios de los datos JSON de Next.js."""
        listings = []
        
        try:
            # Navegar por la estructura de Next.js
            props = data.get('props', {}).get('pageProps', {})
            ads = props.get('realEstateAds', []) or props.get('ads', []) or props.get('listings', [])
            
            for ad in ads:
                listing = {
                    'portal_id': ad.get('id'),
                    'url': urljoin(self.base_url, f"/annonce/{ad.get('id')}") if ad.get('id') else None,
                    'title': ad.get('title', ''),
                    'price': ad.get('price'),
                    'city': ad.get('city', {}).get('name') if isinstance(ad.get('city'), dict) else ad.get('city'),
                    'postal_code': ad.get('postalCode') or ad.get('zipCode'),
                    'surface': ad.get('surfaceArea') or ad.get('surface'),
                    'bedrooms': ad.get('roomsQuantity') or ad.get('rooms'),
                    'description': ad.get('description', '')[:500],
                    'latitude': ad.get('blurredCoordinates', {}).get('lat') if ad.get('blurredCoordinates') else None,
                    'longitude': ad.get('blurredCoordinates', {}).get('lon') if ad.get('blurredCoordinates') else None,
                    'images': ad.get('photos', [])[:5] if isinstance(ad.get('photos'), list) else [],
                }
                
                # Características
                listing['has_elevator'] = ad.get('hasElevator')
                listing['has_parking'] = ad.get('hasParking') or ad.get('parkingPlacesQuantity', 0) > 0
                listing['has_terrace'] = ad.get('hasTerrace')
                listing['has_pool'] = ad.get('hasSwimmingPool')
                listing['floor'] = ad.get('floor')
                
                if listing.get('url'):
                    listings.append(listing)
                    
        except Exception as e:
            self.logger.debug(f"Error extrayendo JSON: {e}")
        
        return listings
    
    def parse_listing_detail(self, html: str, url: str) -> Dict[str, Any]:
        """Parsea la página de detalle de un anuncio."""
        soup = BeautifulSoup(html, 'html.parser')
        data = {'url': url}
        
        # Intentar extraer de JSON primero
        script_data = soup.find('script', {'id': '__NEXT_DATA__'})
        if script_data:
            try:
                json_data = json.loads(script_data.string)
                ad = json_data.get('props', {}).get('pageProps', {}).get('ad', {})
                if ad:
                    data.update({
                        'portal_id': ad.get('id'),
                        'title': ad.get('title', ''),
                        'price': ad.get('price'),
                        'description': ad.get('description', ''),
                        'city': ad.get('city', {}).get('name') if isinstance(ad.get('city'), dict) else ad.get('city'),
                        'address': ad.get('address'),
                        'postal_code': ad.get('postalCode'),
                        'surface': ad.get('surfaceArea'),
                        'bedrooms': ad.get('roomsQuantity'),
                        'bathrooms': ad.get('bathroomsQuantity'),
                        'floor': ad.get('floor'),
                        'has_elevator': ad.get('hasElevator'),
                        'has_parking': ad.get('hasParking'),
                        'has_terrace': ad.get('hasTerrace'),
                        'has_pool': ad.get('hasSwimmingPool'),
                        'has_ac': ad.get('hasAirConditioning'),
                        'latitude': ad.get('coordinates', {}).get('lat'),
                        'longitude': ad.get('coordinates', {}).get('lon'),
                        'images': ad.get('photos', []),
                        'agency': ad.get('publisher', {}).get('name') if ad.get('publisher') else None,
                    })
                    return data
            except json.JSONDecodeError:
                pass
        
        # Fallback a parsing HTML
        title = soup.select_one('h1, .ad-title')
        if title:
            data['title'] = title.get_text(strip=True)
        
        price = soup.select_one('.ad-price, .price')
        if price:
            data['price'] = price.get_text(strip=True)
        
        desc = soup.select_one('.ad-description, .description')
        if desc:
            data['description'] = desc.get_text(strip=True)[:2000]
        
        # Características
        features = soup.select('.ad-features li, .features-list li')
        for feat in features:
            text = feat.get_text(strip=True).lower()
            if 'chambre' in text or 'pièce' in text or 'habitacion' in text:
                match = re.search(r'(\d+)', text)
                if match:
                    data['bedrooms'] = match.group(1)
            elif 'salle de bain' in text or 'baño' in text:
                match = re.search(r'(\d+)', text)
                if match:
                    data['bathrooms'] = match.group(1)
            elif 'm²' in text or 'superficie' in text:
                match = re.search(r'(\d+)', text)
                if match:
                    data['surface'] = match.group(1)
            elif 'étage' in text or 'planta' in text:
                data['floor'] = text
            elif 'ascenseur' in text or 'ascensor' in text:
                data['has_elevator'] = True
            elif 'parking' in text or 'garaje' in text:
                data['has_parking'] = True
            elif 'piscine' in text or 'piscina' in text:
                data['has_pool'] = True
            elif 'terrasse' in text or 'terraza' in text:
                data['has_terrace'] = True
        
        # Imágenes
        images = soup.select('.ad-photos img, .gallery img')
        data['images'] = [urljoin(self.base_url, img.get('src')) for img in images[:15] if img.get('src')]
        
        return data
    
    def get_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Buscar link siguiente
        next_link = soup.select_one('a[rel="next"], .pagination__next a, a.next')
        if next_link and next_link.get('href'):
            return urljoin(self.base_url, next_link['href'])
        
        # Buscar en datos JSON
        script_data = soup.find('script', {'id': '__NEXT_DATA__'})
        if script_data:
            try:
                data = json.loads(script_data.string)
                pagination = data.get('props', {}).get('pageProps', {}).get('pagination', {})
                if pagination.get('hasNextPage'):
                    current_page = pagination.get('currentPage', 1)
                    if '?' in current_url:
                        return f"{current_url}&page={current_page + 1}"
                    else:
                        return f"{current_url}?page={current_page + 1}"
            except json.JSONDecodeError:
                pass
        
        return None
