"""
Funciones auxiliares y utilidades para el bot inmobiliario.
"""

import hashlib
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse

import yaml
from dotenv import load_dotenv


def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """
    Carga la configuración desde archivo YAML.
    Soporta variables de entorno con sintaxis ${VAR_NAME}.
    
    Args:
        config_path: Ruta al archivo de configuración
    
    Returns:
        Diccionario con la configuración
    """
    # Cargar variables de entorno
    load_dotenv()
    
    config_file = Path(config_path)
    
    # Intentar cargar config local primero
    local_config = config_file.parent / f"{config_file.stem}.local{config_file.suffix}"
    if local_config.exists():
        config_file = local_config
    
    with open(config_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Reemplazar variables de entorno
    def replace_env_var(match):
        var_name = match.group(1)
        return os.getenv(var_name, match.group(0))
    
    content = re.sub(r'\$\{(\w+)\}', replace_env_var, content)
    
    return yaml.safe_load(content)


def load_filters(filters_path: str = "config/filters.yaml") -> Dict[str, Any]:
    """
    Carga los filtros de búsqueda desde archivo YAML.
    
    Args:
        filters_path: Ruta al archivo de filtros
    
    Returns:
        Diccionario con los filtros
    """
    filters_file = Path(filters_path)
    
    # Intentar cargar filtros locales primero
    local_filters = filters_file.parent / f"{filters_file.stem}.local{filters_file.suffix}"
    if local_filters.exists():
        filters_file = local_filters
    
    with open(filters_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def generate_listing_id(url: str, portal: str) -> str:
    """
    Genera un ID único para un anuncio basado en su URL y portal.
    
    Args:
        url: URL del anuncio
        portal: Nombre del portal
    
    Returns:
        Hash MD5 truncado como ID único
    """
    content = f"{portal}:{url}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


def clean_price(price_str: str) -> Optional[int]:
    """
    Limpia y convierte un string de precio a entero.
    
    Args:
        price_str: String con el precio (ej: "250.000 €", "150,000€")
    
    Returns:
        Precio como entero o None si no se puede parsear
    """
    if not price_str:
        return None
    
    # Eliminar caracteres no numéricos excepto comas y puntos
    cleaned = re.sub(r'[^\d.,]', '', price_str)
    
    if not cleaned:
        return None
    
    # Manejar formatos europeos (250.000) y americanos (250,000)
    if '.' in cleaned and ',' in cleaned:
        # Formato mixto: determinar cuál es el separador decimal
        if cleaned.rindex('.') > cleaned.rindex(','):
            # Punto es decimal (formato americano)
            cleaned = cleaned.replace(',', '')
        else:
            # Coma es decimal (formato europeo)
            cleaned = cleaned.replace('.', '').replace(',', '.')
    elif '.' in cleaned:
        # Solo puntos: si hay más de uno, son separadores de miles
        if cleaned.count('.') > 1:
            cleaned = cleaned.replace('.', '')
        elif len(cleaned.split('.')[-1]) == 3:
            # Probablemente separador de miles
            cleaned = cleaned.replace('.', '')
    elif ',' in cleaned:
        # Solo comas: si hay más de una, son separadores de miles
        if cleaned.count(',') > 1:
            cleaned = cleaned.replace(',', '')
        elif len(cleaned.split(',')[-1]) == 3:
            # Probablemente separador de miles
            cleaned = cleaned.replace(',', '')
        else:
            # Probablemente separador decimal
            cleaned = cleaned.replace(',', '.')
    
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def clean_surface(surface_str: str) -> Optional[int]:
    """
    Limpia y convierte un string de superficie a entero (m²).
    
    Args:
        surface_str: String con la superficie (ej: "85 m²", "120m2")
    
    Returns:
        Superficie como entero o None si no se puede parsear
    """
    if not surface_str:
        return None
    
    # Buscar número antes de m², m2, metros, etc.
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:m[²2]|metros)', surface_str.lower())
    if match:
        try:
            return int(float(match.group(1).replace(',', '.')))
        except ValueError:
            return None
    
    # Intentar extraer cualquier número
    numbers = re.findall(r'\d+', surface_str)
    if numbers:
        try:
            return int(numbers[0])
        except ValueError:
            return None
    
    return None


def clean_rooms(rooms_str: str) -> Optional[int]:
    """
    Limpia y convierte un string de habitaciones a entero.
    
    Args:
        rooms_str: String con habitaciones (ej: "3 hab", "2 dormitorios")
    
    Returns:
        Número de habitaciones o None
    """
    if not rooms_str:
        return None
    
    # Buscar número
    match = re.search(r'(\d+)', rooms_str)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    
    return None


def normalize_url(url: str, base_url: str = None) -> str:
    """
    Normaliza una URL, convirtiéndola a absoluta si es necesario.
    
    Args:
        url: URL a normalizar
        base_url: URL base para URLs relativas
    
    Returns:
        URL normalizada
    """
    if not url:
        return ""
    
    url = url.strip()
    
    # Si es relativa y tenemos base_url, convertir a absoluta
    if base_url and not url.startswith(('http://', 'https://')):
        url = urljoin(base_url, url)
    
    return url


def random_delay(min_seconds: float = 3, max_seconds: float = 5) -> None:
    """
    Espera un tiempo aleatorio entre peticiones.
    
    Args:
        min_seconds: Mínimo de segundos a esperar
        max_seconds: Máximo de segundos a esperar
    """
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def get_domain(url: str) -> str:
    """
    Extrae el dominio de una URL.
    
    Args:
        url: URL completa
    
    Returns:
        Dominio (ej: "idealista.com")
    """
    parsed = urlparse(url)
    return parsed.netloc.lower().replace('www.', '')


def format_price(price: int) -> str:
    """
    Formatea un precio para mostrar.
    
    Args:
        price: Precio en euros
    
    Returns:
        String formateado (ej: "250.000 €")
    """
    return f"{price:,.0f} €".replace(',', '.')


def format_surface(surface: int) -> str:
    """
    Formatea una superficie para mostrar.
    
    Args:
        surface: Superficie en m²
    
    Returns:
        String formateado (ej: "85 m²")
    """
    return f"{surface} m²"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Trunca un texto a una longitud máxima.
    
    Args:
        text: Texto a truncar
        max_length: Longitud máxima
        suffix: Sufijo a añadir si se trunca
    
    Returns:
        Texto truncado
    """
    if not text or len(text) <= max_length:
        return text or ""
    
    return text[:max_length - len(suffix)].strip() + suffix


def parse_date(date_str: str) -> Optional[datetime]:
    """
    Intenta parsear una fecha en varios formatos comunes.
    
    Args:
        date_str: String con la fecha
    
    Returns:
        Objeto datetime o None
    """
    if not date_str:
        return None
    
    date_str = date_str.strip().lower()
    
    # Patrones comunes
    patterns = [
        '%d/%m/%Y',
        '%d-%m-%Y',
        '%Y-%m-%d',
        '%d/%m/%y',
        '%d de %B de %Y',
        '%d %B %Y',
    ]
    
    # Manejar fechas relativas
    if 'hoy' in date_str:
        return datetime.now()
    if 'ayer' in date_str:
        return datetime.now().replace(day=datetime.now().day - 1)
    
    for pattern in patterns:
        try:
            return datetime.strptime(date_str, pattern)
        except ValueError:
            continue
    
    return None


def matches_filter(listing: Dict[str, Any], filters: Dict[str, Any], strict: bool = False) -> bool:
    """
    Comprueba si un anuncio cumple con los filtros especificados.

    Args:
        listing: Datos del anuncio
        filters: Filtros a aplicar
        strict: Si True, rechaza anuncios sin datos cuando hay filtros activos

    Returns:
        True si cumple todos los filtros, False en caso contrario
    """
    # Filtro de precio
    price_filter = filters.get('price', {})
    if price_filter.get('min') or price_filter.get('max'):
        price = listing.get('price')
        if price is None:
            # No hay precio - en modo estricto, rechazar si hay filtro de precio
            if strict:
                return False
        else:
            if price_filter.get('min') and price < price_filter['min']:
                return False
            if price_filter.get('max') and price > price_filter['max']:
                return False

    # Filtro de superficie
    surface_filter = filters.get('surface', {})
    if surface_filter.get('min') or surface_filter.get('max'):
        surface = listing.get('surface')
        if surface is None:
            # No hay superficie - en modo estricto, rechazar si hay filtro
            if strict:
                return False
        else:
            if surface_filter.get('min') and surface < surface_filter['min']:
                return False
            if surface_filter.get('max') and surface > surface_filter['max']:
                return False

    # Filtro de habitaciones
    bedrooms_filter = filters.get('bedrooms', {})
    if bedrooms_filter.get('min') or bedrooms_filter.get('max'):
        bedrooms = listing.get('bedrooms')
        if bedrooms is None:
            # No hay habitaciones - en modo estricto, rechazar si hay filtro
            if strict:
                return False
        else:
            if bedrooms_filter.get('min') and bedrooms < bedrooms_filter['min']:
                return False
            if bedrooms_filter.get('max') and bedrooms > bedrooms_filter['max']:
                return False

    # Filtro de baños
    bathrooms_filter = filters.get('bathrooms', {})
    if bathrooms_filter.get('min') or bathrooms_filter.get('max'):
        bathrooms = listing.get('bathrooms')
        if bathrooms is None:
            # No hay baños - en modo estricto, rechazar si hay filtro
            if strict:
                return False
        else:
            if bathrooms_filter.get('min') and bathrooms < bathrooms_filter['min']:
                return False
            if bathrooms_filter.get('max') and bathrooms > bathrooms_filter['max']:
                return False

    return True


def ensure_dir(path: Union[str, Path]) -> Path:
    """
    Asegura que un directorio existe, creándolo si es necesario.
    
    Args:
        path: Ruta del directorio
    
    Returns:
        Path del directorio
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_env(key: str, default: Any = None, required: bool = False) -> Any:
    """
    Obtiene una variable de entorno con validación opcional.
    
    Args:
        key: Nombre de la variable
        default: Valor por defecto
        required: Si es obligatoria
    
    Returns:
        Valor de la variable
    
    Raises:
        ValueError: Si es requerida y no existe
    """
    value = os.getenv(key, default)
    
    if required and value is None:
        raise ValueError(f"Variable de entorno requerida no encontrada: {key}")
    
    return value
