"""
Scraper para Idealista.com - Portal líder inmobiliario en España.
https://www.idealista.com

Requires Selenium due to anti-bot protection (JavaScript rendering).
Idealista has very strong anti-bot protection - this scraper uses advanced
evasion techniques including stealth mode, human-like behavior, and
randomized delays.
"""

import random
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .base_scraper import SeleniumBaseScraper


class IdealistaScraper(SeleniumBaseScraper):
    """
    Scraper para Idealista.com using Selenium.

    Idealista es el portal inmobiliario líder en España con más de 50M de visitas
    mensuales y más de 1.2M de anuncios.

    Uses Selenium to bypass anti-bot protection and JavaScript rendering.
    Includes advanced anti-detection measures.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.base_url = 'https://www.idealista.com'
        self.name = 'idealista'
        self._cookies_accepted = False
        # Longer delays for Idealista due to strong anti-bot
        self.min_delay = max(self.min_delay, 5)
        self.max_delay = max(self.max_delay, 10)

    def _handle_cookie_consent(self):
        """Try to accept cookie consent popup - Idealista uses didomi."""
        if self._cookies_accepted:
            return

        try:
            # Idealista uses Didomi for cookie consent
            cookie_selectors = [
                "#didomi-notice-agree-button",  # Didomi accept button
                "button[id*='didomi'][id*='agree']",
                "button[id*='accept']",
                ".didomi-continue-without-agreeing",
                "button[class*='accept']",
                "#onetrust-accept-btn-handler",
                ".cookie-accept",
                "[data-testid='accept-btn']",
            ]

            for selector in cookie_selectors:
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for btn in buttons:
                        if btn.is_displayed():
                            # Use JavaScript click to avoid interception
                            self.driver.execute_script("arguments[0].click();", btn)
                            self._cookies_accepted = True
                            self.logger.debug(f"Cookie consent accepted via: {selector}")
                            time.sleep(1)
                            return
                except Exception:
                    continue

            # Try XPath for Spanish text
            xpath_selectors = [
                "//button[contains(text(), 'Aceptar')]",
                "//button[contains(text(), 'Acepto')]",
                "//button[contains(text(), 'Aceptar y cerrar')]",
                "//span[contains(text(), 'Aceptar')]/parent::button",
                "//button[@id='didomi-notice-agree-button']",
            ]
            for xpath in xpath_selectors:
                try:
                    buttons = self.driver.find_elements(By.XPATH, xpath)
                    for btn in buttons:
                        if btn.is_displayed():
                            self.driver.execute_script("arguments[0].click();", btn)
                            self._cookies_accepted = True
                            self.logger.debug("Cookie consent accepted via XPath")
                            time.sleep(1)
                            return
                except Exception:
                    continue

        except Exception as e:
            self.logger.debug(f"Cookie consent handling: {e}")

    def _simulate_human_behavior(self):
        """Simulate human-like behavior to avoid detection."""
        try:
            # Random scroll
            scroll_amount = random.randint(200, 500)
            self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(random.uniform(0.5, 1.5))

            # Scroll back a bit
            self.driver.execute_script(f"window.scrollBy(0, -{random.randint(50, 150)});")
            time.sleep(random.uniform(0.3, 0.8))

            # Random mouse movement (if possible)
            try:
                body = self.driver.find_element(By.TAG_NAME, "body")
                action = ActionChains(self.driver)
                action.move_to_element_with_offset(
                    body,
                    random.randint(100, 500),
                    random.randint(100, 300)
                ).perform()
            except Exception:
                pass

        except Exception as e:
            self.logger.debug(f"Human behavior simulation: {e}")

    def _check_for_captcha(self, html: str) -> bool:
        """Check if page shows a captcha or block message."""
        captcha_indicators = [
            'captcha',
            'robot',
            'blocked',
            'access denied',
            'acceso denegado',
            'too many requests',
            'rate limit',
            'verificar',
            'datadome',
            'challenge',
        ]
        html_lower = html.lower()
        for indicator in captcha_indicators:
            if indicator in html_lower:
                return True
        return False

    def _fetch_page(self, url: str) -> Optional[str]:
        """
        Override to add extra anti-detection measures for Idealista.

        Idealista has very strong anti-bot protection, so we need:
        - Longer waits
        - Cookie consent handling
        - Human-like behavior simulation
        - Captcha detection
        """
        if not self._can_fetch(url):
            self.logger.warning(f"URL bloqueada por robots.txt: {url}")
            return None

        self._apply_delay()

        try:
            self.logger.debug(f"Fetching Idealista URL: {url}")
            self.driver.get(url)

            # Initial wait for page load
            time.sleep(random.uniform(3, 5))

            # Handle cookie consent
            self._handle_cookie_consent()
            time.sleep(1)

            # Simulate human behavior
            self._simulate_human_behavior()

            # Wait for content to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "article"))
                )
            except Exception:
                self.logger.debug("No article elements found, continuing anyway")

            # More scrolling to trigger lazy loading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 4);")
            time.sleep(random.uniform(1, 2))
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            time.sleep(random.uniform(1, 2))
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.75);")
            time.sleep(random.uniform(0.5, 1))

            # Scroll back to top
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)

            self._last_request_time = time.time()

            html = self.driver.page_source
            self.logger.debug(f"Idealista page fetched: {len(html)} bytes")

            # Check for captcha/block
            if self._check_for_captcha(html):
                self.logger.warning(f"⚠️  Idealista: Captcha or block detected! Page size: {len(html)} bytes")
                # Save page for debugging
                if len(html) < 5000:
                    self.logger.debug(f"Blocked page content preview: {html[:1000]}")
                return None

            # Check if we got a real page (should have significant content)
            if len(html) < 2000:
                self.logger.warning(f"⚠️  Idealista: Page too small ({len(html)} bytes), likely blocked")
                return None

            return html

        except Exception as e:
            self.logger.error(f"Error getting {url}: {e}")
            return None

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

        # Log page title for debugging
        title_tag = soup.find('title')
        if title_tag:
            self.logger.debug(f"Page title: {title_tag.get_text()}")

        # Try multiple selectors for Idealista property cards
        selectors_to_try = [
            ('article', {'class': re.compile(r'item')}),
            ('article', {'class': re.compile(r'item-multimedia-container')}),
            ('div', {'class': re.compile(r'item-info-container')}),
            ('article', {}),
            ('div', {'class': re.compile(r'listing-item|property-card')}),
        ]

        items = []
        for tag, attrs in selectors_to_try:
            items = soup.find_all(tag, attrs) if attrs else soup.find_all(tag)
            if items:
                self.logger.debug(f"Idealista: Found {len(items)} items with selector ({tag}, {attrs})")
                break

        if not items:
            # Fallback: CSS selectors
            items = soup.select('article, .item-info-container, .property-card, [data-adid]')
            self.logger.debug(f"Idealista: Found {len(items)} items with fallback CSS selector")

        self.logger.debug(f"🔍 Idealista: Found {len(items)} items in HTML ({len(html)} bytes)")

        for item in items:
            try:
                listing = self._parse_listing_item(item)
                if listing.get('url'):
                    listings.append(listing)
            except Exception as e:
                self.logger.debug(f"Error parsing Idealista item: {e}")
                continue

        # If no items found, try direct link extraction as last resort
        if not listings:
            self.logger.warning("Idealista: No items found, trying direct link extraction")
            all_links = soup.find_all('a', href=re.compile(r'/inmueble/'))
            for link in all_links:
                href = link.get('href', '')
                if href and '/inmueble/' in href:
                    listing = {'url': urljoin(self.base_url, href)}
                    title = link.get_text(strip=True)
                    if title and len(title) > 5:
                        listing['title'] = title
                    # Try to extract data from context
                    self._extract_data_from_context(link, listing)
                    if listing.get('url') not in [l.get('url') for l in listings]:
                        listings.append(listing)

            self.logger.debug(f"Idealista: Extracted {len(listings)} listings from direct links")

        return listings

    def _extract_data_from_context(self, link, listing: Dict[str, Any]):
        """Extract price/surface/bedrooms from the link's parent container."""
        parent = link.parent
        for _ in range(5):  # Go up max 5 levels
            if parent is None:
                break
            parent_text = parent.get_text(separator=' ', strip=True)

            # Look for price pattern
            if not listing.get('price'):
                price_match = re.search(r'(\d{1,3}(?:[.,]\d{3})*)\s*€', parent_text)
                if price_match:
                    listing['price'] = price_match.group(0)

            # Look for surface pattern
            if not listing.get('surface'):
                surface_match = re.search(r'(\d+)\s*m[²2]', parent_text)
                if surface_match:
                    listing['surface'] = surface_match.group(0)

            # Look for bedrooms pattern
            if not listing.get('bedrooms'):
                bedrooms_match = re.search(r'(\d+)\s*(?:hab|dormitorio|habitacion)', parent_text, re.IGNORECASE)
                if bedrooms_match:
                    listing['bedrooms'] = bedrooms_match.group(0)

            # Look for bathrooms pattern
            if not listing.get('bathrooms'):
                bathrooms_match = re.search(r'(\d+)\s*(?:baño|aseo)', parent_text, re.IGNORECASE)
                if bathrooms_match:
                    listing['bathrooms'] = bathrooms_match.group(0)

            if listing.get('price') and listing.get('surface'):
                break

            parent = parent.parent

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
