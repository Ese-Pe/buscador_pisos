#!/usr/bin/env python3
"""
Tool to inspect real estate website HTML structure.
Helps identify correct CSS selectors for scraping.
"""

import requests
from bs4 import BeautifulSoup
import json
from typing import Dict, Any, List
import re


def fetch_and_analyze(url: str) -> Dict[str, Any]:
    """
    Fetches a URL and analyzes its HTML structure.
    Returns information about potential selectors for listings.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Get page title
        title = soup.find('title')
        page_title = title.get_text(strip=True) if title else "No title"

        # Find potential listing containers
        potential_containers = find_listing_containers(soup)

        # Find potential price elements
        potential_prices = find_price_elements(soup)

        # Find potential links
        potential_links = find_listing_links(soup)

        # Get body structure sample
        body = soup.find('body')
        body_classes = body.get('class', []) if body else []

        # Main content divs
        main_divs = soup.find_all(['div', 'main', 'section'], class_=True, limit=20)
        main_div_classes = [div.get('class') for div in main_divs if div.get('class')]

        return {
            'url': url,
            'status': 'success',
            'page_title': page_title,
            'body_classes': body_classes,
            'main_div_classes': main_div_classes[:10],
            'potential_containers': potential_containers,
            'potential_prices': potential_prices,
            'potential_links': potential_links,
            'response_length': len(response.text),
        }

    except requests.exceptions.RequestException as e:
        return {
            'url': url,
            'status': 'error',
            'error': str(e)
        }


def find_listing_containers(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Find elements that might be property listing containers."""
    containers = []

    # Common patterns for listing containers
    patterns = [
        ('article', None),  # semantic HTML
        ('div', re.compile(r'.*card.*', re.I)),
        ('div', re.compile(r'.*property.*', re.I)),
        ('div', re.compile(r'.*listing.*', re.I)),
        ('div', re.compile(r'.*item.*', re.I)),
        ('div', re.compile(r'.*inmueble.*', re.I)),
        ('div', re.compile(r'.*anuncio.*', re.I)),
        ('li', re.compile(r'.*property.*', re.I)),
    ]

    for tag, class_pattern in patterns:
        if class_pattern:
            elements = soup.find_all(tag, class_=class_pattern, limit=5)
        else:
            elements = soup.find_all(tag, limit=5)

        if elements:
            for elem in elements:
                # Check if it contains price-like text
                text = elem.get_text(separator=' ', strip=True)
                has_price = bool(re.search(r'\d+[.,]\d{3}.*€', text))
                has_link = bool(elem.find('a', href=True))

                if has_price or has_link:
                    containers.append({
                        'tag': tag,
                        'classes': elem.get('class', []),
                        'id': elem.get('id'),
                        'has_price': has_price,
                        'has_link': has_link,
                        'text_sample': text[:150],
                    })

    return containers[:10]


def find_price_elements(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """Find elements that contain price information."""
    prices = []

    # Look for elements with price-like text
    price_pattern = re.compile(r'\d+[.,]\d{3}.*€|€\s*\d+[.,]\d{3}')

    # Check common price containers
    for tag in ['span', 'div', 'p', 'strong']:
        elements = soup.find_all(tag, class_=re.compile(r'.*(price|precio).*', re.I), limit=10)
        for elem in elements:
            text = elem.get_text(strip=True)
            if price_pattern.search(text):
                prices.append({
                    'tag': tag,
                    'classes': ' '.join(elem.get('class', [])),
                    'text': text,
                })

    # Also search in all text
    all_with_prices = soup.find_all(string=price_pattern, limit=10)
    for text in all_with_prices:
        parent = text.parent
        if parent and parent.name:
            prices.append({
                'tag': parent.name,
                'classes': ' '.join(parent.get('class', [])),
                'text': text.strip(),
            })

    return prices[:10]


def find_listing_links(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """Find links that might point to property details."""
    links = []

    # Common URL patterns for property listings
    patterns = [
        r'/inmueble/',
        r'/vivienda/',
        r'/anuncio/',
        r'/propiedad/',
        r'/property/',
        r'/piso/',
        r'/casa/',
    ]

    for pattern in patterns:
        link_elements = soup.find_all('a', href=re.compile(pattern, re.I), limit=5)
        for link in link_elements:
            links.append({
                'href': link.get('href', ''),
                'text': link.get_text(strip=True)[:100],
                'classes': ' '.join(link.get('class', [])),
            })

    return links[:15]


def generate_selector_suggestions(analysis: Dict[str, Any]) -> List[str]:
    """Generate CSS selector suggestions based on analysis."""
    suggestions = []

    # From containers
    for container in analysis.get('potential_containers', []):
        classes = container.get('classes', [])
        if classes:
            selector = f"{container['tag']}.{'.'.join(classes)}"
            suggestions.append(selector)

    # From main divs
    for div_classes in analysis.get('main_div_classes', []):
        if div_classes and any('result' in c.lower() or 'list' in c.lower() for c in div_classes):
            suggestions.append(f"div.{'.'.join(div_classes)}")

    return suggestions[:5]


def main():
    """Main function to test website inspection."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python inspect_website.py <URL>")
        print("\nExample URLs to test:")
        print("  Tucasa: https://www.tucasa.com/compra-venta/viviendas/zaragoza/zaragoza-capital/")
        print("  Altamira: https://www.altamirainmuebles.com/inmuebles/viviendas?provincia=Zaragoza")
        print("  Solvia: https://www.solvia.es/inmuebles?provincia=Zaragoza")
        return

    url = sys.argv[1]

    print(f"🔍 Inspecting: {url}\n")
    print("=" * 80)

    analysis = fetch_and_analyze(url)

    if analysis['status'] == 'error':
        print(f"❌ Error: {analysis['error']}")
        return

    print(f"✅ Status: {analysis['status']}")
    print(f"📄 Page Title: {analysis['page_title']}")
    print(f"📊 Response Length: {analysis['response_length']:,} bytes")
    print()

    print("=" * 80)
    print("POTENTIAL LISTING CONTAINERS:")
    print("=" * 80)
    for i, container in enumerate(analysis['potential_containers'], 1):
        print(f"\n{i}. <{container['tag']}> with classes: {container['classes']}")
        if container.get('id'):
            print(f"   ID: {container['id']}")
        print(f"   Has price: {container['has_price']}")
        print(f"   Has link: {container['has_link']}")
        print(f"   Sample: {container['text_sample']}")

    print("\n" + "=" * 80)
    print("POTENTIAL PRICE ELEMENTS:")
    print("=" * 80)
    for i, price in enumerate(analysis['potential_prices'], 1):
        print(f"\n{i}. <{price['tag']}> classes=\"{price['classes']}\"")
        print(f"   Text: {price['text']}")

    print("\n" + "=" * 80)
    print("POTENTIAL LISTING LINKS:")
    print("=" * 80)
    for i, link in enumerate(analysis['potential_links'], 1):
        print(f"\n{i}. href=\"{link['href']}\"")
        print(f"   Text: {link['text']}")
        print(f"   Classes: {link['classes']}")

    print("\n" + "=" * 80)
    print("SUGGESTED CSS SELECTORS:")
    print("=" * 80)
    suggestions = generate_selector_suggestions(analysis)
    for i, selector in enumerate(suggestions, 1):
        print(f"{i}. {selector}")

    print("\n" + "=" * 80)
    print(f"\n💡 Use these selectors to update the scraper for: {url}")
    print()


if __name__ == "__main__":
    main()
