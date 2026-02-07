"""
Scraper para Habitaclia.com - Portal inmobiliario popular en España.
https://www.habitaclia.com

Requires Selenium due to JavaScript rendering and anti-bot protection.
"""

import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
        self._cookies_accepted = False

    def _handle_cookie_consent(self):
        """Try to accept cookie consent popup."""
        if self._cookies_accepted:
            return

        try:
            # Common cookie consent button selectors for Habitaclia
            cookie_selectors = [
                "#didomi-notice-agree-button",
                "button[id*='accept']",
                "button[class*='accept']",
                ".didomi-continue-without-agreeing",
                "#onetrust-accept-btn-handler",
                ".cookie-accept",
                "button[data-action='accept']",
            ]

            for selector in cookie_selectors:
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for btn in buttons:
                        if btn.is_displayed():
                            btn.click()
                            self._cookies_accepted = True
                            self.logger.debug("Cookie consent accepted")
                            time.sleep(1)
                            return
                except Exception:
                    continue

            # Try XPath for Spanish text
            xpath_selectors = [
                "//button[contains(text(), 'Aceptar')]",
                "//button[contains(text(), 'Acepto')]",
                "//button[contains(text(), 'Entendido')]",
                "//button[contains(text(), 'Agree')]",
                "//span[contains(text(), 'Aceptar')]/parent::button",
            ]
            for xpath in xpath_selectors:
                try:
                    buttons = self.driver.find_elements(By.XPATH, xpath)
                    for btn in buttons:
                        if btn.is_displayed():
                            btn.click()
                            self._cookies_accepted = True
                            self.logger.debug("Cookie consent accepted via XPath")
                            time.sleep(1)
                            return
                except Exception:
                    continue

        except Exception as e:
            self.logger.debug(f"Cookie consent handling: {e}")

    def _fetch_page(self, url: str) -> Optional[str]:
        """Override to add cookie handling and extra wait for Habitaclia."""
        if not self._can_fetch(url):
            return None

        self._apply_delay()

        try:
            self.driver.get(url)
            time.sleep(3)

            # Handle cookie consent
            self._handle_cookie_consent()

            time.sleep(2)

            # Scroll to trigger lazy loading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 3);")
            time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            time.sleep(1)

            self._last_request_time = time.time()

            html = self.driver.page_source
            self.logger.debug(f"Habitaclia page fetched: {len(html)} bytes")

            return html

        except Exception as e:
            self.logger.error(f"Error getting {url}: {e}")
            return None

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

        # Try multiple selectors for Habitaclia property cards
        selectors_to_try = [
            ('div', {'class': 'list-item'}),
            ('article', {'class': re.compile(r'item|listing|property')}),
            ('div', {'class': re.compile(r'property-card|listing-item|search-result')}),
            ('li', {'class': re.compile(r'item|listing')}),
            ('article', {}),
        ]

        items = []
        for tag, attrs in selectors_to_try:
            if attrs:
                items = soup.find_all(tag, attrs)
            else:
                items = soup.find_all(tag)
            if items:
                self.logger.debug(f"Habitaclia: Found {len(items)} items with selector ({tag}, {attrs})")
                break

        self.logger.debug(f"Habitaclia: Found {len(items)} items in HTML ({len(html)} bytes)")

        # If no items found, try to find property links directly
        if not items:
            self.logger.warning("Habitaclia: No item containers found, trying direct link extraction")
            all_links = soup.find_all('a', href=re.compile(r'/vivienda|/piso|/casa|/inmueble|/comprar'))
            for link in all_links:
                href = link.get('href', '')
                if href and len(href) > 20:  # Skip short navigation links
                    listing = {'url': urljoin(self.base_url, href)}
                    title = link.get_text(strip=True)
                    if title and len(title) > 5:
                        listing['title'] = title
                    if listing.get('url') not in [l.get('url') for l in listings]:
                        listings.append(listing)
            self.logger.debug(f"Habitaclia: Extracted {len(listings)} URLs from direct links")
            return listings

        for item in items:
            try:
                listing = self._parse_listing_item(item)
                if listing.get('url'):
                    listings.append(listing)
                    self.logger.debug(f"Habitaclia: Extracted URL: {listing.get('url')}")
            except Exception as e:
                self.logger.debug(f"Error parsing Habitaclia item: {e}")
                continue

        # If we found items but no URLs, try extracting URLs directly
        if not listings and items:
            self.logger.warning(f"Habitaclia: Found {len(items)} containers but extracted 0 URLs. Trying direct link extraction.")
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                if any(x in href for x in ['/vivienda', '/piso', '/casa', '/inmueble']):
                    if href not in [l.get('url') for l in listings]:
                        listing = {'url': urljoin(self.base_url, href)}
                        title = link.get_text(strip=True)
                        if title and len(title) > 5:
                            listing['title'] = title
                        listings.append(listing)

        self.logger.info(f"Habitaclia: Total listings extracted: {len(listings)}")
        return listings

    def _parse_listing_item(self, item: BeautifulSoup) -> Dict[str, Any]:
        """Extrae datos de un item de Habitaclia."""
        listing = {}

        # URL and Title - try multiple patterns
        link = None

        # Pattern 1: list-item-title
        title_link = item.find('a', class_='list-item-title')
        if title_link:
            link = title_link

        # Pattern 2: Any link with property-related path
        if not link:
            link = item.find('a', href=re.compile(r'/vivienda|/piso|/casa|/inmueble|/comprar'))

        # Pattern 3: First valid link
        if not link:
            for a in item.find_all('a', href=True):
                href = a.get('href', '')
                if href and not href.startswith('#') and 'javascript:' not in href and len(href) > 10:
                    link = a
                    break

        if link and link.get('href'):
            listing['url'] = urljoin(self.base_url, link.get('href'))
            if not listing.get('title'):
                listing['title'] = link.get_text(strip=True)

        # Título - try multiple selectors
        if not listing.get('title'):
            title_elem = item.find(['h1', 'h2', 'h3', 'h4', 'h5'])
            if not title_elem:
                title_elem = item.find(class_=re.compile(r'title|titulo|heading'))
            if title_elem:
                listing['title'] = title_elem.get_text(strip=True)

        # Precio - try multiple patterns
        price_elem = item.find(class_=re.compile(r'price|precio|list-item-price'))
        if not price_elem:
            price_elem = item.find(string=re.compile(r'€|EUR|\d+\.\d+'))
        if price_elem:
            if hasattr(price_elem, 'get_text'):
                listing['price'] = price_elem.get_text(strip=True)
            else:
                listing['price'] = str(price_elem).strip()

        # Ubicación
        location_elem = item.find(class_=re.compile(r'location|ubicacion|list-item-location|ciudad|localidad'))
        if location_elem:
            listing['city'] = location_elem.get_text(strip=True)

        # Características
        features = item.find_all(class_=re.compile(r'feature|caracteristica|list-item-feature|info|spec'))
        for feature in features:
            text = feature.get_text(strip=True).lower()

            if 'm²' in text or 'm2' in text:
                listing['surface'] = text
            elif 'hab' in text or 'habitacion' in text or 'dorm' in text:
                listing['bedrooms'] = text
            elif 'baño' in text:
                listing['bathrooms'] = text

        # Descripción
        desc_elem = item.find(class_=re.compile(r'description|descripcion|list-item-description'))
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
