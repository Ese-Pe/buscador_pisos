"""
Scraper genérico configurable para portales inmobiliarios.
Permite definir selectores CSS personalizados por portal.
"""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, SeleniumBaseScraper


class GenericScraper(BaseScraper):
    """
    Scraper genérico que puede configurarse para diferentes portales.
    
    Usa un diccionario de selectores CSS para extraer información.
    """
    
    def __init__(self, config: Dict[str, Any] = None, portal_config: Dict[str, Any] = None):
        super().__init__(config)
        self.portal_config = portal_config or {}
        
        # Configuración del portal
        self.name = self.portal_config.get('name', 'generic')
        self.base_url = self.portal_config.get('base_url', '')
        self.search_path = self.portal_config.get('search_path', '/buscar')
        
        # Selectores CSS
        self.selectors = self.portal_config.get('selectors', {})
    
    def build_search_url(self, filters: Dict[str, Any]) -> str:
        """Construye URL según la configuración del portal."""
        param_mapping = self.portal_config.get('param_mapping', {})
        params = {}
        
        # Mapear filtros a parámetros
        location = filters.get('location', {})
        if location.get('province') and param_mapping.get('province'):
            params[param_mapping['province']] = location['province']
        if location.get('city') and param_mapping.get('city'):
            params[param_mapping['city']] = location['city']
        
        if filters.get('price', {}).get('min') and param_mapping.get('price_min'):
            params[param_mapping['price_min']] = filters['price']['min']
        if filters.get('price', {}).get('max') and param_mapping.get('price_max'):
            params[param_mapping['price_max']] = filters['price']['max']
        
        if filters.get('surface', {}).get('min') and param_mapping.get('surface_min'):
            params[param_mapping['surface_min']] = filters['surface']['min']
        
        if filters.get('bedrooms', {}).get('min') and param_mapping.get('bedrooms_min'):
            params[param_mapping['bedrooms_min']] = filters['bedrooms']['min']
        
        # Tipo de operación
        if filters.get('operation_type') and param_mapping.get('operation_type'):
            op_map = param_mapping.get('operation_values', {'compra': 'venta', 'alquiler': 'alquiler'})
            params[param_mapping['operation_type']] = op_map.get(filters['operation_type'], 'venta')
        
        url = self.base_url + self.search_path
        if params:
            url += '?' + urlencode(params)
        return url
    
    def parse_listing_list(self, html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, 'html.parser')
        listings = []
        
        # Selector de items
        item_selector = self.selectors.get('item', 'article, .property-card, .listing-item')
        items = soup.select(item_selector)
        
        for item in items:
            try:
                listing = self._extract_item_data(item)
                if listing.get('url'):
                    listings.append(listing)
            except Exception as e:
                self.logger.debug(f"Error parseando item: {e}")
        
        return listings
    
    def _extract_item_data(self, item: BeautifulSoup) -> Dict[str, Any]:
        """Extrae datos de un item usando los selectores configurados."""
        data = {}
        
        # URL
        link_sel = self.selectors.get('link', 'a[href]')
        link = item.select_one(link_sel)
        if link:
            data['url'] = urljoin(self.base_url, link.get('href', ''))
            if not data.get('title'):
                data['title'] = link.get_text(strip=True)
        
        # Título
        title_sel = self.selectors.get('title', 'h2, h3, .title')
        title = item.select_one(title_sel)
        if title:
            data['title'] = title.get_text(strip=True)
        
        # Precio
        price_sel = self.selectors.get('price', '.price, [class*="price"]')
        price = item.select_one(price_sel)
        if price:
            data['price'] = price.get_text(strip=True)
        
        # Ubicación
        loc_sel = self.selectors.get('location', '.location, address')
        location = item.select_one(loc_sel)
        if location:
            data['city'] = location.get_text(strip=True)
        
        # Superficie
        surface_sel = self.selectors.get('surface', '[class*="m2"], [class*="surface"]')
        surface = item.select_one(surface_sel)
        if surface:
            data['surface'] = surface.get_text(strip=True)
        
        # Habitaciones
        rooms_sel = self.selectors.get('bedrooms', '[class*="room"], [class*="hab"]')
        rooms = item.select_one(rooms_sel)
        if rooms:
            data['bedrooms'] = rooms.get_text(strip=True)
        
        # Baños
        bath_sel = self.selectors.get('bathrooms', '[class*="bath"], [class*="baño"]')
        bath = item.select_one(bath_sel)
        if bath:
            data['bathrooms'] = bath.get_text(strip=True)
        
        # Imagen
        img_sel = self.selectors.get('image', 'img')
        img = item.select_one(img_sel)
        if img:
            img_url = img.get('src') or img.get('data-src') or img.get('data-lazy')
            if img_url:
                data['images'] = [urljoin(self.base_url, img_url)]
        
        return data
    
    def parse_listing_detail(self, html: str, url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, 'html.parser')
        data = {'url': url}
        
        detail_selectors = self.selectors.get('detail', {})
        
        # Título
        title_sel = detail_selectors.get('title', 'h1')
        title = soup.select_one(title_sel)
        if title:
            data['title'] = title.get_text(strip=True)
        
        # Precio
        price_sel = detail_selectors.get('price', '.price')
        price = soup.select_one(price_sel)
        if price:
            data['price'] = price.get_text(strip=True)
        
        # Descripción
        desc_sel = detail_selectors.get('description', '.description')
        desc = soup.select_one(desc_sel)
        if desc:
            data['description'] = desc.get_text(strip=True)[:2000]
        
        # Características
        features_sel = detail_selectors.get('features', '.features li, .characteristics li')
        features = soup.select(features_sel)
        for feat in features:
            text = feat.get_text(strip=True).lower()
            self._parse_feature(text, data)
        
        # Imágenes
        gallery_sel = detail_selectors.get('gallery', '.gallery img, .photos img')
        images = soup.select(gallery_sel)
        data['images'] = []
        for img in images[:15]:
            img_url = img.get('src') or img.get('data-src')
            if img_url:
                data['images'].append(urljoin(self.base_url, img_url))
        
        return data
    
    def _parse_feature(self, text: str, data: Dict[str, Any]):
        """Parsea una característica y la añade a los datos."""
        if 'habitacion' in text or 'dormitorio' in text:
            match = re.search(r'(\d+)', text)
            if match:
                data['bedrooms'] = match.group(1)
        elif 'baño' in text:
            match = re.search(r'(\d+)', text)
            if match:
                data['bathrooms'] = match.group(1)
        elif 'm²' in text or 'm2' in text or 'metro' in text:
            match = re.search(r'(\d+)', text)
            if match:
                data['surface'] = match.group(1)
        elif 'planta' in text:
            data['floor'] = text
        elif 'ascensor' in text:
            data['has_elevator'] = 'sin' not in text and 'no ' not in text
        elif 'garaje' in text or 'parking' in text or 'plaza' in text:
            data['has_parking'] = 'sin' not in text and 'no ' not in text
        elif 'piscina' in text:
            data['has_pool'] = 'sin' not in text and 'no ' not in text
        elif 'trastero' in text:
            data['has_storage'] = 'sin' not in text and 'no ' not in text
        elif 'terraza' in text:
            data['has_terrace'] = 'sin' not in text and 'no ' not in text
        elif 'aire acondicionado' in text or 'a/a' in text:
            data['has_ac'] = 'sin' not in text and 'no ' not in text
        elif 'calefaccion' in text or 'calefacción' in text:
            data['has_heating'] = 'sin' not in text and 'no ' not in text
    
    def get_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        soup = BeautifulSoup(html, 'html.parser')
        
        next_sel = self.selectors.get('next_page', 'a.next, a[rel="next"], .pagination .next a')
        next_link = soup.select_one(next_sel)
        
        if next_link and next_link.get('href'):
            href = next_link.get('href')
            if href and href != '#':
                return urljoin(self.base_url, href)
        
        return None


# Configuraciones predefinidas para portales bancarios
PORTAL_CONFIGS = {
    'altamira': {
        'name': 'altamira',
        'base_url': 'https://www.altamirainmuebles.com',
        'search_path': '/inmuebles/viviendas',
        'param_mapping': {
            'province': 'provincia',
            'city': 'localidad',
            'price_min': 'precioDesde',
            'price_max': 'precioHasta',
            'surface_min': 'superficieDesde',
            'bedrooms_min': 'habitaciones',
        },
        'selectors': {
            'item': '.property-card, .inmueble-card, article',
            'link': 'a[href*="/inmueble/"]',
            'title': '.title, h3',
            'price': '.price, .precio',
            'location': '.location, .ubicacion',
            'surface': '.surface, .superficie',
            'bedrooms': '.rooms, .habitaciones',
            'next_page': '.pagination .next a, a[rel="next"]',
        }
    },
    'solvia': {
        'name': 'solvia',
        'base_url': 'https://www.solvia.es',
        'search_path': '/inmuebles',
        'param_mapping': {
            'province': 'provincia',
            'city': 'municipio',
            'price_min': 'precioMin',
            'price_max': 'precioMax',
            'surface_min': 'superficieMin',
            'bedrooms_min': 'habitaciones',
            'operation_type': 'tipoOperacion',
            'operation_values': {'compra': 'venta', 'alquiler': 'alquiler'},
        },
        'selectors': {
            'item': '.property-card, .item-inmueble',
            'link': 'a[href*="/inmueble"]',
            'title': '.title, h2, h3',
            'price': '.price, .precio',
            'location': '.location, .ubicacion',
            'next_page': '.pagination .next, a.next',
        }
    },
    'haya': {
        'name': 'haya',
        'base_url': 'https://www.haya.es',
        'search_path': '/comprar/viviendas',
        'param_mapping': {
            'province': 'provincia',
            'price_max': 'precio_hasta',
            'surface_min': 'metros_desde',
        },
        'selectors': {
            'item': '.property-item, .inmueble',
            'link': 'a[href*="/inmueble/"]',
            'title': '.title, h3',
            'price': '.price, .precio',
            'location': '.location',
        }
    },
    'servihabitat': {
        'name': 'servihabitat',
        'base_url': 'https://www.servihabitat.com',
        'search_path': '/viviendas',
        'param_mapping': {
            'province': 'provincia',
            'city': 'localidad',
            'price_max': 'precioHasta',
        },
        'selectors': {
            'item': '.property-card, .vivienda-item',
            'link': 'a[href*="/vivienda/"]',
            'price': '.price, .precio',
        }
    },
    'aliseda': {
        'name': 'aliseda',
        'base_url': 'https://www.alisedainmobiliaria.com',
        'search_path': '/venta/viviendas',
        'param_mapping': {
            'province': 'provincia',
            'price_max': 'precio_max',
        },
        'selectors': {
            'item': '.property-item, article',
            'link': 'a[href*="/inmueble/"]',
            'price': '.price',
        }
    },
    'anticipa': {
        'name': 'anticipa',
        'base_url': 'https://www.anticipa.es',
        'search_path': '/inmuebles',
        'param_mapping': {
            'province': 'provincia',
            'price_max': 'precio_hasta',
        },
        'selectors': {
            'item': '.property-card',
            'link': 'a[href*="/inmueble"]',
            'price': '.price',
        }
    },
    'bbva_valora': {
        'name': 'bbva_valora',
        'base_url': 'https://www.bbvavivienda.com',
        'search_path': '/viviendas-en-venta',
        'param_mapping': {
            'province': 'provincia',
            'city': 'municipio',
            'price_max': 'precioMaximo',
        },
        'selectors': {
            'item': '.property-card, .vivienda',
            'link': 'a[href*="/vivienda/"]',
            'price': '.price, .precio',
        }
    },
    'bankinter': {
        'name': 'bankinter',
        'base_url': 'https://habitat.bankinter.com',
        'search_path': '/inmuebles',
        'param_mapping': {
            'province': 'provincia',
        },
        'selectors': {
            'item': '.property-item',
            'link': 'a[href*="/inmueble"]',
        }
    },
    'kutxabank': {
        'name': 'kutxabank',
        'base_url': 'https://inmobiliaria.kutxabank.es',
        'search_path': '/venta-viviendas',
        'param_mapping': {
            'province': 'provincia',
        },
        'selectors': {
            'item': '.property-card',
            'link': 'a[href*="/vivienda/"]',
        }
    },
    'cajamar': {
        'name': 'cajamar',
        'base_url': 'https://www.cajamarvidainmobiliaria.es',
        'search_path': '/buscador',
        'param_mapping': {
            'province': 'provincia',
        },
        'selectors': {
            'item': '.property-item',
        }
    },
    'ibercaja': {
        'name': 'ibercaja',
        'base_url': 'https://www.ibercajaorienta.es',
        'search_path': '/inmuebles',
        'param_mapping': {
            'province': 'provincia',
        },
        'selectors': {
            'item': '.inmueble-card',
        }
    },
    'comprarcasa': {
        'name': 'comprarcasa',
        'base_url': 'https://www.comprarcasa.com',
        'search_path': '/venta/viviendas',
        'param_mapping': {
            'province': 'zona',
            'price_max': 'precioMax',
        },
        'selectors': {
            'item': '.property-item, .vivienda',
            'link': 'a[href*="/vivienda/"]',
        }
    },
}


def create_portal_scraper(portal_name: str, config: Dict[str, Any] = None) -> GenericScraper:
    """
    Crea un scraper para un portal específico.
    
    Args:
        portal_name: Nombre del portal
        config: Configuración general
    
    Returns:
        GenericScraper configurado
    """
    portal_config = PORTAL_CONFIGS.get(portal_name)
    if not portal_config:
        raise ValueError(f"Portal no soportado: {portal_name}")
    
    return GenericScraper(config=config, portal_config=portal_config)
