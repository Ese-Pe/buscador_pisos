"""
Scraper para Haya Real Estate - Portal de propiedades bancarias.
https://www.haya.es

Haya gestiona activos inmobiliarios de CaixaBank, Bankia y otros bancos.
Requires Selenium due to JavaScript and anti-bot protection.
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


class HayaScraper(SeleniumBaseScraper):
    """
    Scraper para Haya Real Estate using Selenium.

    Haya es uno de los mayores servicers inmobiliarios de España,
    gestionando activos de CaixaBank, Bankia y otros bancos.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.base_url = 'https://www.haya.es'
        self.name = 'haya'
        self._cookies_accepted = False

    def _handle_cookie_consent(self):
        """Try to accept cookie consent popup."""
        if self._cookies_accepted:
            return

        try:
            # Common cookie consent button selectors
            cookie_selectors = [
                "button[id*='accept']",
                "button[class*='accept']",
                "a[id*='accept']",
                ".cookie-accept",
                "#acceptCookies",
                "button[data-action='accept']",
                "[class*='cookie'] button",
                "[id*='cookie'] button",
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
                "//a[contains(text(), 'Aceptar')]",
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
        """Override to add extra wait time for Haya's JavaScript."""
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
            self.logger.debug(f"Haya page fetched: {len(html)} bytes")

            return html

        except Exception as e:
            self.logger.error(f"Error getting {url}: {e}")
            return None

    def build_search_url(self, filters: Dict[str, Any]) -> str:
        """
        Construye URL de búsqueda de Haya.

        Formato: /comprar/viviendas/{province}/
        Ejemplo: /comprar/viviendas/zaragoza/
        """
        location = filters.get('location', {})
        province = location.get('province', '').lower()

        province = self._normalize_for_url(province)

        operation = filters.get('operation_type', 'compra')
        if operation in ['compra', 'venta']:
            operation_path = 'comprar'
        else:
            operation_path = 'alquilar'

        # Haya format: /comprar/viviendas/{province}/
        if province:
            url = f"{self.base_url}/{operation_path}/viviendas/{province}/"
        else:
            url = f"{self.base_url}/{operation_path}/viviendas/"

        self.logger.info(f"Haya search URL: {url}")
        return url

    def _normalize_for_url(self, text: str) -> str:
        """Normaliza texto para URL."""
        if not text:
            return ''

        text = text.lower().strip()

        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'ñ': 'n', 'ü': 'u', 'à': 'a', 'è': 'e', 'ì': 'i',
            'ò': 'o', 'ù': 'u', 'ç': 'c'
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        text = text.replace(' ', '-')
        return text

    def parse_listing_list(self, html: str) -> List[Dict[str, Any]]:
        """Parsea la página de listado de Haya."""
        soup = BeautifulSoup(html, 'html.parser')
        listings = []

        # Try multiple selectors for Haya property cards
        selectors_to_try = [
            ('div', {'class': re.compile(r'property-card|inmueble-card|asset-card')}),
            ('article', {}),
            ('div', {'class': re.compile(r'card.*property|property.*card')}),
            ('div', {'class': re.compile(r'resultado|result')}),
            ('li', {'class': re.compile(r'property|inmueble|asset')}),
        ]

        items = []
        for tag, attrs in selectors_to_try:
            items = soup.find_all(tag, attrs) if attrs else soup.find_all(tag)
            if items:
                self.logger.debug(f"Haya: Found {len(items)} items with selector ({tag}, {attrs})")
                break

        if not items:
            items = soup.select('.card, .listing-item, .resultado-item, [data-id]')
            self.logger.debug(f"Haya: Found {len(items)} items with fallback CSS selector")

        # Also try to find all links that look like property URLs
        if not items:
            all_links = soup.find_all('a', href=re.compile(r'/comprar/|/inmueble|/vivienda|/activo|/piso'))
            self.logger.debug(f"Haya: Found {len(all_links)} property links directly")
            for link in all_links:
                href = link.get('href', '')
                if href and '/comprar/' in href:
                    listing = {'url': urljoin(self.base_url, href)}
                    title = link.get_text(strip=True)
                    if title:
                        listing['title'] = title
                    listings.append(listing)
            return listings

        for item in items:
            try:
                listing = self._parse_listing_item(item)
                if listing.get('url'):
                    listings.append(listing)
                    self.logger.debug(f"Haya: Extracted URL: {listing.get('url')}")
            except Exception as e:
                self.logger.debug(f"Error parsing Haya item: {e}")
                continue

        # If we found items but no URLs, try extracting URLs directly from html
        if not listings and items:
            self.logger.warning(f"Haya: Found {len(items)} containers but extracted 0 URLs. Trying direct link extraction.")
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                # Look for links that look like property detail pages
                if '/comprar/' in href or '/inmueble/' in href or '/vivienda/' in href:
                    if href not in [l.get('url') for l in listings]:
                        listing = {'url': urljoin(self.base_url, href)}
                        title = link.get_text(strip=True)
                        if title and len(title) > 5:
                            listing['title'] = title
                        # Try to find price/surface in parent container
                        self._extract_data_from_context(link, listing)
                        listings.append(listing)

        self.logger.info(f"Haya: Total listings extracted: {len(listings)}")
        return listings

    def _parse_listing_item(self, item: BeautifulSoup) -> Dict[str, Any]:
        """Extrae datos de un item de Haya."""
        listing = {}

        # Try multiple patterns for URL extraction
        link = None

        # Pattern 1: Links with property-related paths
        link = item.find('a', href=re.compile(r'/comprar/|/inmueble|/vivienda|/activo|/piso'))

        # Pattern 2: Any link with href
        if not link:
            all_links = item.find_all('a', href=True)
            for a in all_links:
                href = a.get('href', '')
                # Skip navigation/pagination links
                if href and not href.startswith('#') and not 'javascript:' in href:
                    if any(x in href for x in ['/comprar/', '/inmueble', '/vivienda', '/activo', '/piso']):
                        link = a
                        break

        # Pattern 3: First valid link
        if not link:
            for a in item.find_all('a', href=True):
                href = a.get('href', '')
                if href and not href.startswith('#') and 'javascript:' not in href and len(href) > 10:
                    link = a
                    break

        if link and link.get('href'):
            href = link.get('href')
            listing['url'] = urljoin(self.base_url, href)
            self.logger.debug(f"Haya item URL: {listing['url']}")

        # Título - try multiple selectors
        title_elem = item.find(['h1', 'h2', 'h3', 'h4', 'h5'])
        if not title_elem:
            title_elem = item.find(class_=re.compile(r'title|titulo|nombre|heading'))
        if not title_elem and link:
            title_elem = link
        if title_elem:
            listing['title'] = title_elem.get_text(strip=True)

        # Precio - try multiple patterns
        price_elem = item.find(class_=re.compile(r'price|precio|importe|coste'))
        if not price_elem:
            price_elem = item.find(string=re.compile(r'€|EUR|\d+\.\d+'))
        if price_elem:
            if hasattr(price_elem, 'get_text'):
                listing['price'] = price_elem.get_text(strip=True)
            else:
                listing['price'] = str(price_elem).strip()

        # Ubicación
        location_elem = item.find(class_=re.compile(r'location|ubicacion|direccion|localidad|ciudad'))
        if location_elem:
            listing['city'] = location_elem.get_text(strip=True)

        # Características
        features = item.find_all(class_=re.compile(r'feature|caracteristica|detalle|info|spec'))
        for feature in features:
            text = feature.get_text(strip=True).lower()

            if 'm²' in text or 'm2' in text:
                listing['surface'] = text
            elif 'hab' in text or 'dormitorio' in text:
                listing['bedrooms'] = text
            elif 'baño' in text:
                listing['bathrooms'] = text

        # Imagen
        img_elem = item.find('img')
        if img_elem:
            img_src = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-lazy')
            if img_src and not img_src.startswith('data:'):
                listing['images'] = [img_src]

        return listing

    def _extract_data_from_context(self, link, listing: Dict[str, Any]):
        """Extract price/surface/bedrooms from the link's parent container."""
        # Go up to find a meaningful parent container
        parent = link.parent
        for _ in range(5):  # Go up max 5 levels
            if parent is None:
                break
            parent_text = parent.get_text(separator=' ', strip=True)

            # Look for price pattern (e.g., "85.000 €", "120000€")
            if not listing.get('price'):
                price_match = re.search(r'(\d{1,3}(?:[.,]\d{3})*)\s*€', parent_text)
                if price_match:
                    listing['price'] = price_match.group(0)

            # Look for surface pattern (e.g., "90 m²", "120m2")
            if not listing.get('surface'):
                surface_match = re.search(r'(\d+)\s*m[²2]', parent_text)
                if surface_match:
                    listing['surface'] = surface_match.group(0)

            # Look for bedrooms pattern (e.g., "3 hab", "2 dormitorios")
            if not listing.get('bedrooms'):
                bedrooms_match = re.search(r'(\d+)\s*(?:hab|dormitorio|habitacion)', parent_text, re.IGNORECASE)
                if bedrooms_match:
                    listing['bedrooms'] = bedrooms_match.group(0)

            # Look for bathrooms pattern
            if not listing.get('bathrooms'):
                bathrooms_match = re.search(r'(\d+)\s*(?:baño|aseo)', parent_text, re.IGNORECASE)
                if bathrooms_match:
                    listing['bathrooms'] = bathrooms_match.group(0)

            # If we found price and surface, we can stop
            if listing.get('price') and listing.get('surface'):
                break

            parent = parent.parent

    def parse_listing_detail(self, html: str, url: str) -> Dict[str, Any]:
        """Parsea la página de detalle."""
        return {}

    def get_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        """Extrae URL de la siguiente página."""
        soup = BeautifulSoup(html, 'html.parser')

        next_link = soup.find('a', class_=re.compile(r'next|siguiente'))

        if not next_link:
            pagination = soup.find(class_=re.compile(r'pagination'))
            if pagination:
                next_link = pagination.find('a', rel='next')

        if next_link and next_link.get('href'):
            return urljoin(self.base_url, next_link.get('href'))

        return None
