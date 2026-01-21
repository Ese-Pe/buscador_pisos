"""
Scraper para el portal Tucasa.com
Agregador de anuncios inmobiliarios en España.
URL correcta: https://www.tucasa.com/compra-venta/viviendas/{provincia}/{ciudad}/
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
    
    # Mapeo de tipos de propiedad
    PROPERTY_TYPES = {
        'piso': 'pisos-y-apartamentos',
        'casa': 'casas-y-chalets', 
        'atico': 'aticos',
        'duplex': 'duplex',
        'estudio': 'estudios',
        'chalet': 'casas-y-chalets',
        'todos': 'viviendas',
    }
    
    def build_search_url(self, filters: Dict[str, Any]) -> str:
        """
        Construye la URL de búsqueda para Tucasa.
        
        Formato correcto: /compra-venta/viviendas/{provincia}/{ciudad-capital}/
        Ejemplo: https://www.tucasa.com/compra-venta/viviendas/zaragoza/zaragoza-capital/
        """
        # Tipo de propiedad
        property_type = self.PROPERTY_TYPES.get(
            filters.get('property_type', 'todos'),
            'viviendas'
        )
        
        # Ubicación
        location = filters.get('location', {})
        province = self._normalize_location(location.get('province', ''))
        city = self._normalize_location(location.get('city', ''))
        
        # Si la ciudad es igual a la provincia, añadir "-capital"
        if city and city == province:
            city = f"{city}-capital"
        
        # Construir path
        if city and province:
            path = f"/compra-venta/{property_type}/{province}/{city}/"
        elif province:
            path = f"/compra-venta/{property_type}/{province}/"
        else:
            path = f"/compra-venta/{property_type}/"
        
        # Parámetros de filtro (Tucasa usa query params diferentes)
        params = {}
        
        # Precio
        if filters.get('price', {}).get('min'):
            params['pmin'] = filters['price']['min']
        if filters.get('price', {}).get('max'):
            params['pmax'] = filters['price']['max']
        
        # Superficie
        if filters.get('surface', {}).get('min'):
            params['smin'] = filters['surface']['min']
        if filters.get('surface', {}).get('max'):
            params['smax'] = filters['surface']['max']
        
        # Habitaciones
        if filters.get('bedrooms', {}).get('min'):
            params['hmin'] = filters['bedrooms']['min']
        
        # Baños
        if filters.get('bathrooms', {}).get('min'):
            params['bmin'] = filters['bathrooms']['min']
        
        # Construir URL final
        url = self.base_url + path
        if params:
            url += '?' + urlencode(params)
        
        return url
    
    def _normalize_location(self, location: str) -> str:
        """Normaliza el nombre de ubicación para la URL."""
        if not location:
            return ''
        
        # Convertir a minúsculas
        normalized = location.lower().strip()
        
        # Reemplazar espacios por guiones
        normalized = normalized.replace(' ', '-')
        
        # Reemplazar acentos
        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'ñ': 'n', 'ü': 'u'
        }
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        
        return normalized
    
    def parse_listing_list(self, html: str) -> List[Dict[str, Any]]:
        """
        Parsea la página de listado de Tucasa.

        Tucasa usa Livewire (Laravel) y los datos están en atributos wire:initial-data
        como JSON embebido, no en HTML tradicional.
        """
        import json
        import html as html_lib

        soup = BeautifulSoup(html, 'html.parser')
        listings = []

        # Log HTML title for debugging
        title = soup.find('title')
        if title:
            self.logger.debug(f"Page title: {title.get_text(strip=True)}")

        # Buscar componentes Livewire con nombre "inmueble-listado"
        livewire_components = soup.find_all('div', {'wire:initial-data': True})

        self.logger.debug(f"Found {len(livewire_components)} Livewire components")

        listing_components = []
        for component in livewire_components:
            try:
                data_attr = component.get('wire:initial-data', '')
                # Decodificar HTML entities
                data_json_str = html_lib.unescape(data_attr)
                data = json.loads(data_json_str)

                # Verificar que sea un componente de tipo inmueble-listado
                if data.get('fingerprint', {}).get('name') == 'inmueble-listado':
                    listing_components.append(data)

            except (json.JSONDecodeError, AttributeError) as e:
                self.logger.debug(f"Error parsing Livewire component: {e}")
                continue

        self.logger.debug(f"Found {len(listing_components)} inmueble-listado components")

        if listing_components:
            # Parsear datos de Livewire
            for component_data in listing_components:
                try:
                    listing = self._parse_livewire_listing(component_data)
                    if listing.get('url'):
                        listings.append(listing)
                except Exception as e:
                    self.logger.debug(f"Error parseando Livewire listing: {e}")
                    continue
        else:
            # Fallback al método antiguo si no hay componentes Livewire
            self.logger.warning("No Livewire components found, trying old HTML parsing method")
            listings = self._parse_traditional_html(soup)

        return listings
    
    def _parse_livewire_listing(self, component_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parsea un listing desde datos Livewire JSON.

        Args:
            component_data: Diccionario con datos del componente Livewire

        Returns:
            Diccionario con datos del listing
        """
        listing = {}

        # Extraer datos del inmueble desde serverMemo.data.inmueble
        inmueble = component_data.get('serverMemo', {}).get('data', {}).get('inmueble', {})

        if not inmueble:
            return listing

        # URL
        url = component_data.get('serverMemo', {}).get('data', {}).get('url', '')
        if url:
            listing['url'] = urljoin(self.base_url, url)

        # Título
        titulo = inmueble.get('titulo', '')
        calle = inmueble.get('calle', '')
        listing['title'] = f"{titulo} - {calle}" if titulo and calle else (titulo or calle or 'Sin título')

        # Precio
        precio = inmueble.get('eurosinmueble')
        if precio:
            try:
                precio_float = float(precio)
                listing['price'] = f"{int(precio_float):,} €".replace(',', '.')
            except (ValueError, TypeError):
                listing['price'] = str(precio)

        # Ubicación
        if calle:
            listing['city'] = calle
        zona_info = inmueble.get('arbolzona', '')
        if zona_info:
            # Parse: "Provincia: Zaragoza&&Comarca: Zaragoza Capital&&Localidad: Zaragoza Capital&&Distrito: Centro&&Barrio: "
            parts = zona_info.split('&&')
            for part in parts:
                if 'Distrito:' in part:
                    listing['district'] = part.split(':')[-1].strip()

        # Superficie
        metros_construidos = inmueble.get('metrosconstruidosinmueble')
        metros_utiles = inmueble.get('metrosutilesinmueble')
        if metros_construidos:
            listing['surface'] = str(metros_construidos)
        elif metros_utiles:
            listing['surface'] = str(metros_utiles)

        # Habitaciones
        dormitorios = inmueble.get('dormitoriosinmueble')
        if dormitorios:
            listing['bedrooms'] = str(dormitorios)

        # Baños
        banyos = inmueble.get('banyosinmueble')
        if banyos:
            listing['bathrooms'] = str(banyos)

        # Imágenes
        imagenes_array = inmueble.get('imagenesarraycache', '')
        if imagenes_array:
            # Es una cadena separada por comas
            listing['images'] = imagenes_array.split(',')[:5]  # Primeras 5 imágenes
        else:
            imagen_principal = inmueble.get('imagenprincipal', '')
            if imagen_principal:
                listing['images'] = [f"https://www.tucasa.com/cacheimg/small/{imagen_principal[-2:]}/{imagen_principal}.jpg"]

        # Descripción
        comentario = inmueble.get('comentarioinmueble', '')
        if comentario:
            listing['description'] = comentario[:500]  # Primeros 500 caracteres

        # Referencia
        referencia = inmueble.get('referenciainmueble', '')
        if referencia:
            listing['reference'] = referencia

        # ID del inmueble
        id_inmueble = inmueble.get('idinmueble', '')
        if id_inmueble:
            listing['property_id'] = id_inmueble

        return listing

    def _parse_traditional_html(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Método fallback para parsear HTML tradicional.
        Usado si no se encuentran componentes Livewire.
        """
        listings = []

        # Intentar varios selectores comunes
        selectors = [
            'article.anuncio',
            'div.property-card',
            'div.listing-item',
            'li.property-item',
            'div.inmueble_listado',
            '.resultados article',
        ]

        items = []
        for selector in selectors:
            items = soup.select(selector)
            if items:
                self.logger.debug(f"✓ Encontrados {len(items)} items con selector: {selector}")
                break
            else:
                self.logger.debug(f"✗ No items con selector: {selector}")

        if not items:
            # Intentar buscar enlaces de anuncios directamente
            links = soup.select('a[href*="/inmueble/"], a[href*="/anuncio/"], a[href*="/pisos-y-apartamentos/"]')
            self.logger.debug(f"Búsqueda de enlaces: encontrados {len(links)} enlaces")

            if not links:
                self.logger.warning(f"⚠️ No se encontraron anuncios ni enlaces en la página")
                return listings

            for link in links:
                parent = link.find_parent(['article', 'div', 'li'])
                if parent and parent not in items:
                    items.append(parent)

        for item in items:
            try:
                listing = self._parse_listing_item(item)
                if listing.get('url'):
                    listings.append(listing)
            except Exception as e:
                self.logger.debug(f"Error parseando item: {e}")
                continue

        return listings

    def _parse_listing_item(self, item) -> Dict[str, Any]:
        """Parsea un item individual del listado."""
        listing = {}
        
        # URL - buscar varios patrones
        link = item.select_one('a[href*="/inmueble/"], a[href*="/anuncio/"], a[href*="idanuncio"]')
        if not link:
            link = item.select_one('a[href]')
        
        if link:
            href = link.get('href', '')
            if href and '/inmueble/' in href or '/anuncio/' in href or 'idanuncio' in href:
                listing['url'] = urljoin(self.base_url, href)
                # Título del enlace
                listing['title'] = link.get('title', '') or link.get_text(strip=True)
        
        # Título alternativo
        title = item.select_one('h2, h3, .titulo, .title, .property-title')
        if title:
            listing['title'] = title.get_text(strip=True)
        
        # Precio - buscar varios patrones
        price_selectors = ['.precio', '.price', '.property-price', '[class*="precio"]', 'span.price']
        for sel in price_selectors:
            price = item.select_one(sel)
            if price:
                listing['price'] = price.get_text(strip=True)
                break
        
        # Ubicación
        location_selectors = ['.ubicacion', '.location', '.localidad', '.property-location', 'address']
        for sel in location_selectors:
            location = item.select_one(sel)
            if location:
                loc_text = location.get_text(strip=True)
                listing['city'] = loc_text
                break
        
        # Características - superficie, habitaciones, baños
        # Buscar en texto o atributos data-*
        text_content = item.get_text(separator=' ', strip=True).lower()
        
        # Superficie
        surface_match = re.search(r'(\d+)\s*m[²2]', text_content)
        if surface_match:
            listing['surface'] = surface_match.group(1)
        
        # Habitaciones
        rooms_match = re.search(r'(\d+)\s*(?:hab|dorm|habitacion)', text_content)
        if rooms_match:
            listing['bedrooms'] = rooms_match.group(1)
        
        # Baños
        bath_match = re.search(r'(\d+)\s*baño', text_content)
        if bath_match:
            listing['bathrooms'] = bath_match.group(1)
        
        # Imagen
        img = item.select_one('img[src], img[data-src], img[data-lazy-src]')
        if img:
            img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if img_url and not img_url.startswith('data:'):
                listing['images'] = [urljoin(self.base_url, img_url)]
        
        return listing
    
    def parse_listing_detail(self, html: str, url: str) -> Dict[str, Any]:
        """Parsea la página de detalle de un anuncio."""
        soup = BeautifulSoup(html, 'html.parser')
        data = {'url': url}
        
        # Título
        title = soup.select_one('h1, .property-title, .titulo-anuncio')
        if title:
            data['title'] = title.get_text(strip=True)
        
        # Precio
        price = soup.select_one('.precio, .price, .property-price')
        if price:
            data['price'] = price.get_text(strip=True)
        
        # Descripción
        desc = soup.select_one('.descripcion, .description, .property-description, #descripcion')
        if desc:
            data['description'] = desc.get_text(strip=True)[:2000]
        
        # Dirección
        address = soup.select_one('.direccion, .address, .ubicacion-completa')
        if address:
            data['address'] = address.get_text(strip=True)
        
        # Características - buscar en tabla o lista
        features = soup.select('.caracteristicas li, .features li, .datos-basicos li, table.datos tr')
        for feat in features:
            text = feat.get_text(strip=True).lower()
            self._parse_feature(text, data)
        
        # Buscar también en texto general
        main_content = soup.select_one('.ficha-inmueble, .property-details, main')
        if main_content:
            text = main_content.get_text(separator=' ', strip=True).lower()
            
            if 'surface' not in data:
                surface_match = re.search(r'(\d+)\s*m[²2]', text)
                if surface_match:
                    data['surface'] = surface_match.group(1)
            
            if 'bedrooms' not in data:
                rooms_match = re.search(r'(\d+)\s*(?:hab|dorm)', text)
                if rooms_match:
                    data['bedrooms'] = rooms_match.group(1)
        
        # Imágenes de la galería
        images = soup.select('.galeria img, .gallery img, .fotos img, [class*="slider"] img')
        data['images'] = []
        for img in images[:15]:
            img_url = img.get('src') or img.get('data-src')
            if img_url and not img_url.startswith('data:'):
                data['images'].append(urljoin(self.base_url, img_url))
        
        # Agencia/Anunciante
        agency = soup.select_one('.anunciante, .inmobiliaria, .agency, .advertiser')
        if agency:
            data['agency'] = agency.get_text(strip=True)
        
        # Teléfono
        phone = soup.select_one('a[href^="tel:"], .telefono, .phone')
        if phone:
            data['contact_phone'] = phone.get('href', '').replace('tel:', '') or phone.get_text(strip=True)
        
        return data
    
    def _parse_feature(self, text: str, data: Dict[str, Any]):
        """Parsea una característica y la añade a los datos."""
        # Superficie
        if 'm²' in text or 'm2' in text or 'metros' in text or 'superficie' in text:
            match = re.search(r'(\d+)', text)
            if match and 'surface' not in data:
                data['surface'] = match.group(1)
        
        # Habitaciones
        elif 'habitacion' in text or 'dormitorio' in text or 'dorm' in text:
            match = re.search(r'(\d+)', text)
            if match and 'bedrooms' not in data:
                data['bedrooms'] = match.group(1)
        
        # Baños
        elif 'baño' in text or 'aseo' in text:
            match = re.search(r'(\d+)', text)
            if match and 'bathrooms' not in data:
                data['bathrooms'] = match.group(1)
        
        # Planta
        elif 'planta' in text or 'piso' in text:
            if 'floor' not in data:
                data['floor'] = text
        
        # Características booleanas
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
        elif 'aire' in text and 'acondicionado' in text:
            data['has_ac'] = 'sin' not in text and 'no ' not in text
        elif 'calefaccion' in text or 'calefacción' in text:
            data['has_heating'] = 'sin' not in text and 'no ' not in text
        elif 'amueblado' in text:
            data['is_furnished'] = 'sin' not in text and 'no ' not in text
        elif 'exterior' in text:
            data['is_exterior'] = True
    
    def get_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        """Obtiene la URL de la siguiente página."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Buscar link a siguiente página
        next_selectors = [
            'a.siguiente',
            'a[rel="next"]',
            '.pagination .next a',
            '.paginacion a.next',
            'a:contains("Siguiente")',
            'a:contains(">")',
            '.paginas a.activa + a',  # Enlace después del activo
        ]
        
        for selector in next_selectors:
            try:
                next_link = soup.select_one(selector)
                if next_link and next_link.get('href'):
                    href = next_link['href']
                    if href and href != '#' and href != current_url:
                        return urljoin(self.base_url, href)
            except:
                continue
        
        # Buscar por patrón de paginación en URL
        parsed = urlparse(current_url)
        params = parse_qs(parsed.query)
        
        # Tucasa usa 'pgn' para paginación
        current_page = int(params.get('pgn', ['1'])[0])
        
        # Verificar si hay más resultados en la página
        results = soup.select('article, .property-card, .listing-item')
        if results and len(results) >= 10:  # Si hay al menos 10 resultados, probablemente hay más
            new_params = dict(params)
            new_params['pgn'] = [str(current_page + 1)]
            new_query = urlencode({k: v[0] for k, v in new_params.items()})
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"
        
        return None
