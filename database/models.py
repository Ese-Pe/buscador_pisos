"""
Modelos y esquemas de base de datos para el bot inmobiliario.
Define la estructura de datos para anuncios y ejecuciones.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum


class OperationType(Enum):
    """Tipo de operación inmobiliaria."""
    SALE = "compra"
    RENT = "alquiler"


class PropertyType(Enum):
    """Tipo de inmueble."""
    FLAT = "piso"
    HOUSE = "casa"
    PENTHOUSE = "atico"
    DUPLEX = "duplex"
    STUDIO = "estudio"
    CHALET = "chalet"
    OTHER = "otro"


@dataclass
class Listing:
    """
    Modelo de datos para un anuncio inmobiliario.
    """
    # Identificación
    id: str                           # ID único generado
    portal: str                       # Nombre del portal
    portal_id: Optional[str] = None   # ID interno del portal
    url: str = ""                     # URL del anuncio
    
    # Información básica
    title: str = ""                   # Título del anuncio
    description: str = ""             # Descripción
    price: Optional[int] = None       # Precio en euros
    
    # Ubicación
    province: str = ""                # Provincia
    city: str = ""                    # Ciudad
    zone: str = ""                    # Zona/Barrio
    address: str = ""                 # Dirección
    postal_code: str = ""             # Código postal
    latitude: Optional[float] = None  # Latitud
    longitude: Optional[float] = None # Longitud
    
    # Características físicas
    surface: Optional[int] = None     # Superficie en m²
    bedrooms: Optional[int] = None    # Número de habitaciones
    bathrooms: Optional[int] = None   # Número de baños
    floor: Optional[str] = None       # Planta/Piso
    
    # Características adicionales
    has_elevator: Optional[bool] = None
    has_parking: Optional[bool] = None
    has_storage: Optional[bool] = None
    has_pool: Optional[bool] = None
    has_terrace: Optional[bool] = None
    has_ac: Optional[bool] = None
    has_heating: Optional[bool] = None
    is_furnished: Optional[bool] = None
    is_exterior: Optional[bool] = None
    
    # Tipo de propiedad
    operation_type: str = "compra"    # compra, alquiler
    property_type: str = "piso"       # piso, casa, etc.
    
    # Fechas
    publication_date: Optional[datetime] = None
    last_update: Optional[datetime] = None
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    
    # Estado
    is_new: bool = True               # Si es nuevo en esta ejecución
    is_active: bool = True            # Si sigue activo
    
    # Información adicional
    agency: str = ""                  # Inmobiliaria
    contact_phone: str = ""           # Teléfono de contacto
    images: List[str] = field(default_factory=list)  # URLs de imágenes
    raw_data: Dict[str, Any] = field(default_factory=dict)  # Datos originales
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el objeto a diccionario."""
        data = asdict(self)
        # Convertir fechas a string ISO
        for key in ['publication_date', 'last_update', 'first_seen', 'last_seen']:
            if data[key] is not None:
                data[key] = data[key].isoformat()
        # Convertir listas a string JSON
        import json
        data['images'] = json.dumps(data['images'])
        data['raw_data'] = json.dumps(data['raw_data'])
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Listing':
        """Crea un objeto desde un diccionario."""
        import json
        # Convertir strings ISO a fechas
        for key in ['publication_date', 'last_update', 'first_seen', 'last_seen']:
            if data.get(key) and isinstance(data[key], str):
                try:
                    data[key] = datetime.fromisoformat(data[key])
                except ValueError:
                    data[key] = None
        # Convertir JSON strings a listas/dicts
        if isinstance(data.get('images'), str):
            try:
                data['images'] = json.loads(data['images'])
            except json.JSONDecodeError:
                data['images'] = []
        if isinstance(data.get('raw_data'), str):
            try:
                data['raw_data'] = json.loads(data['raw_data'])
            except json.JSONDecodeError:
                data['raw_data'] = {}
        return cls(**data)
    
    def get_location_string(self) -> str:
        """Devuelve la ubicación formateada."""
        parts = []
        if self.zone:
            parts.append(self.zone)
        if self.city:
            parts.append(self.city)
        if self.province and self.province != self.city:
            parts.append(self.province)
        return ", ".join(parts) if parts else "Ubicación no especificada"
    
    def get_features_string(self) -> str:
        """Devuelve las características formateadas."""
        features = []
        if self.bedrooms:
            features.append(f"{self.bedrooms} hab.")
        if self.bathrooms:
            features.append(f"{self.bathrooms} baños")
        if self.surface:
            features.append(f"{self.surface} m²")
        if self.floor:
            features.append(f"Planta {self.floor}")
        return " | ".join(features) if features else ""
    
    def __str__(self) -> str:
        price_str = f"{self.price:,}€".replace(',', '.') if self.price else "Precio no disp."
        return f"{self.title} - {price_str} - {self.get_location_string()}"


@dataclass
class RunStats:
    """
    Estadísticas de una ejecución del bot.
    """
    id: Optional[int] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    # Contadores
    total_listings_found: int = 0
    new_listings: int = 0
    updated_listings: int = 0
    errors: int = 0
    
    # Por portal
    portal_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    # Estado
    status: str = "running"  # running, completed, failed
    error_message: str = ""
    
    # Configuración usada
    profiles_searched: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        import json
        data = asdict(self)
        if data['start_time']:
            data['start_time'] = data['start_time'].isoformat()
        if data['end_time']:
            data['end_time'] = data['end_time'].isoformat()
        data['portal_stats'] = json.dumps(data['portal_stats'])
        data['profiles_searched'] = json.dumps(data['profiles_searched'])
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RunStats':
        """Crea desde diccionario."""
        import json
        if isinstance(data.get('start_time'), str):
            data['start_time'] = datetime.fromisoformat(data['start_time'])
        if isinstance(data.get('end_time'), str):
            data['end_time'] = datetime.fromisoformat(data['end_time'])
        if isinstance(data.get('portal_stats'), str):
            data['portal_stats'] = json.loads(data['portal_stats'])
        if isinstance(data.get('profiles_searched'), str):
            data['profiles_searched'] = json.loads(data['profiles_searched'])
        return cls(**data)
    
    def add_portal_stats(self, portal: str, found: int, new: int, errors: int = 0):
        """Añade estadísticas de un portal."""
        self.portal_stats[portal] = {
            'found': found,
            'new': new,
            'errors': errors
        }
        self.total_listings_found += found
        self.new_listings += new
        self.errors += errors
    
    def complete(self, success: bool = True, error_message: str = ""):
        """Marca la ejecución como completada."""
        self.end_time = datetime.now()
        self.status = "completed" if success else "failed"
        self.error_message = error_message


# SQL para crear las tablas
CREATE_TABLES_SQL = """
-- Tabla de anuncios
CREATE TABLE IF NOT EXISTS listings (
    id TEXT PRIMARY KEY,
    portal TEXT NOT NULL,
    portal_id TEXT,
    url TEXT NOT NULL,
    
    title TEXT,
    description TEXT,
    price INTEGER,
    
    province TEXT,
    city TEXT,
    zone TEXT,
    address TEXT,
    postal_code TEXT,
    latitude REAL,
    longitude REAL,
    
    surface INTEGER,
    bedrooms INTEGER,
    bathrooms INTEGER,
    floor TEXT,
    
    has_elevator INTEGER,
    has_parking INTEGER,
    has_storage INTEGER,
    has_pool INTEGER,
    has_terrace INTEGER,
    has_ac INTEGER,
    has_heating INTEGER,
    is_furnished INTEGER,
    is_exterior INTEGER,
    
    operation_type TEXT DEFAULT 'compra',
    property_type TEXT DEFAULT 'piso',
    
    publication_date TEXT,
    last_update TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    
    is_new INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    
    agency TEXT,
    contact_phone TEXT,
    images TEXT,
    raw_data TEXT,
    
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Índices para búsquedas frecuentes
CREATE INDEX IF NOT EXISTS idx_listings_portal ON listings(portal);
CREATE INDEX IF NOT EXISTS idx_listings_city ON listings(city);
CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price);
CREATE INDEX IF NOT EXISTS idx_listings_first_seen ON listings(first_seen);
CREATE INDEX IF NOT EXISTS idx_listings_is_new ON listings(is_new);
CREATE INDEX IF NOT EXISTS idx_listings_is_active ON listings(is_active);

-- Tabla de estadísticas de ejecución
CREATE TABLE IF NOT EXISTS run_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT NOT NULL,
    end_time TEXT,
    
    total_listings_found INTEGER DEFAULT 0,
    new_listings INTEGER DEFAULT 0,
    updated_listings INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    
    portal_stats TEXT,
    status TEXT DEFAULT 'running',
    error_message TEXT,
    profiles_searched TEXT,
    
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de exclusiones (anuncios ignorados manualmente)
CREATE TABLE IF NOT EXISTS exclusions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id TEXT,
    url TEXT,
    reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(listing_id)
);

-- Tabla de notificaciones enviadas
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id TEXT NOT NULL,
    channel TEXT NOT NULL,  -- 'email' o 'telegram'
    sent_at TEXT NOT NULL,
    status TEXT DEFAULT 'sent',
    error_message TEXT,
    FOREIGN KEY (listing_id) REFERENCES listings(id)
);

CREATE INDEX IF NOT EXISTS idx_notifications_listing ON notifications(listing_id);
CREATE INDEX IF NOT EXISTS idx_notifications_channel ON notifications(channel);
"""
