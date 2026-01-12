"""
Gestor de base de datos SQLite para el bot inmobiliario.
Maneja todas las operaciones CRUD de anuncios y estadísticas.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from .models import Listing, RunStats, CREATE_TABLES_SQL
from utils import get_logger, ensure_dir

logger = get_logger("database")


class DatabaseManager:
    """
    Gestor de base de datos SQLite.
    Implementa el patrón Singleton para compartir conexión.
    """
    
    _instance = None
    
    def __new__(cls, db_path: str = "data/listings.db"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: str = "data/listings.db"):
        if self._initialized:
            return
        
        self.db_path = Path(db_path)
        ensure_dir(self.db_path.parent)
        
        self._connection = None
        self._initialize_db()
        self._initialized = True
        
        logger.info(f"Base de datos inicializada: {self.db_path}")
    
    def _initialize_db(self):
        """Crea las tablas si no existen."""
        with self.get_connection() as conn:
            conn.executescript(CREATE_TABLES_SQL)
            conn.commit()
    
    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager para obtener una conexión a la base de datos.
        
        Yields:
            Conexión SQLite
        """
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    # -------------------------------------------------------------------------
    # OPERACIONES DE ANUNCIOS
    # -------------------------------------------------------------------------
    
    def save_listing(self, listing: Listing) -> bool:
        """
        Guarda o actualiza un anuncio en la base de datos.
        
        Args:
            listing: Objeto Listing a guardar
        
        Returns:
            True si es nuevo, False si ya existía
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Verificar si existe
            cursor.execute("SELECT id, first_seen FROM listings WHERE id = ?", (listing.id,))
            existing = cursor.fetchone()
            
            data = listing.to_dict()
            
            if existing:
                # Actualizar registro existente
                listing.is_new = False
                listing.first_seen = datetime.fromisoformat(existing['first_seen'])
                data = listing.to_dict()
                
                columns = [k for k in data.keys() if k != 'id']
                set_clause = ", ".join([f"{col} = ?" for col in columns])
                values = [data[col] for col in columns]
                values.append(listing.id)
                
                cursor.execute(
                    f"UPDATE listings SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    values
                )
                conn.commit()
                logger.debug(f"Anuncio actualizado: {listing.id}")
                return False
            else:
                # Insertar nuevo
                listing.is_new = True
                data = listing.to_dict()
                
                columns = list(data.keys())
                placeholders = ", ".join(["?" for _ in columns])
                columns_str = ", ".join(columns)
                values = [data[col] for col in columns]
                
                cursor.execute(
                    f"INSERT INTO listings ({columns_str}) VALUES ({placeholders})",
                    values
                )
                conn.commit()
                logger.info(f"Nuevo anuncio guardado: {listing.id} - {listing.title[:50]}")
                return True
    
    def save_listings_batch(self, listings: List[Listing]) -> Tuple[int, int]:
        """
        Guarda múltiples anuncios de forma eficiente.
        
        Args:
            listings: Lista de anuncios
        
        Returns:
            Tupla (nuevos, actualizados)
        """
        new_count = 0
        updated_count = 0
        
        for listing in listings:
            is_new = self.save_listing(listing)
            if is_new:
                new_count += 1
            else:
                updated_count += 1
        
        return new_count, updated_count
    
    def get_listing(self, listing_id: str) -> Optional[Listing]:
        """
        Obtiene un anuncio por su ID.
        
        Args:
            listing_id: ID del anuncio
        
        Returns:
            Objeto Listing o None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM listings WHERE id = ?", (listing_id,))
            row = cursor.fetchone()
            
            if row:
                return Listing.from_dict(dict(row))
            return None
    
    def get_listing_by_url(self, url: str) -> Optional[Listing]:
        """
        Obtiene un anuncio por su URL.
        
        Args:
            url: URL del anuncio
        
        Returns:
            Objeto Listing o None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM listings WHERE url = ?", (url,))
            row = cursor.fetchone()
            
            if row:
                return Listing.from_dict(dict(row))
            return None
    
    def exists(self, listing_id: str) -> bool:
        """
        Verifica si un anuncio existe en la base de datos.
        
        Args:
            listing_id: ID del anuncio
        
        Returns:
            True si existe
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM listings WHERE id = ?", (listing_id,))
            return cursor.fetchone() is not None
    
    def get_new_listings(self, since: datetime = None) -> List[Listing]:
        """
        Obtiene los anuncios nuevos desde una fecha.
        
        Args:
            since: Fecha desde la cual buscar (por defecto, última ejecución)
        
        Returns:
            Lista de anuncios nuevos
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if since:
                cursor.execute(
                    "SELECT * FROM listings WHERE first_seen >= ? ORDER BY first_seen DESC",
                    (since.isoformat(),)
                )
            else:
                cursor.execute(
                    "SELECT * FROM listings WHERE is_new = 1 ORDER BY first_seen DESC"
                )
            
            rows = cursor.fetchall()
            return [Listing.from_dict(dict(row)) for row in rows]
    
    def get_listings_by_portal(
        self,
        portal: str,
        active_only: bool = True
    ) -> List[Listing]:
        """
        Obtiene todos los anuncios de un portal.
        
        Args:
            portal: Nombre del portal
            active_only: Solo anuncios activos
        
        Returns:
            Lista de anuncios
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM listings WHERE portal = ?"
            params = [portal]
            
            if active_only:
                query += " AND is_active = 1"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [Listing.from_dict(dict(row)) for row in rows]
    
    def search_listings(
        self,
        city: str = None,
        province: str = None,
        min_price: int = None,
        max_price: int = None,
        min_surface: int = None,
        max_surface: int = None,
        min_bedrooms: int = None,
        portal: str = None,
        active_only: bool = True,
        limit: int = 100
    ) -> List[Listing]:
        """
        Busca anuncios con filtros.
        
        Returns:
            Lista de anuncios que cumplen los criterios
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            conditions = []
            params = []
            
            if city:
                conditions.append("LOWER(city) LIKE ?")
                params.append(f"%{city.lower()}%")
            
            if province:
                conditions.append("LOWER(province) LIKE ?")
                params.append(f"%{province.lower()}%")
            
            if min_price:
                conditions.append("price >= ?")
                params.append(min_price)
            
            if max_price:
                conditions.append("price <= ?")
                params.append(max_price)
            
            if min_surface:
                conditions.append("surface >= ?")
                params.append(min_surface)
            
            if max_surface:
                conditions.append("surface <= ?")
                params.append(max_surface)
            
            if min_bedrooms:
                conditions.append("bedrooms >= ?")
                params.append(min_bedrooms)
            
            if portal:
                conditions.append("portal = ?")
                params.append(portal)
            
            if active_only:
                conditions.append("is_active = 1")
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            cursor.execute(
                f"SELECT * FROM listings WHERE {where_clause} ORDER BY first_seen DESC LIMIT ?",
                params + [limit]
            )
            
            rows = cursor.fetchall()
            return [Listing.from_dict(dict(row)) for row in rows]
    
    def mark_listings_inactive(self, portal: str, active_ids: List[str]):
        """
        Marca como inactivos los anuncios que ya no aparecen.
        
        Args:
            portal: Nombre del portal
            active_ids: IDs de anuncios que siguen activos
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if active_ids:
                placeholders = ",".join(["?" for _ in active_ids])
                cursor.execute(
                    f"""UPDATE listings 
                        SET is_active = 0, updated_at = CURRENT_TIMESTAMP 
                        WHERE portal = ? AND id NOT IN ({placeholders}) AND is_active = 1""",
                    [portal] + active_ids
                )
            else:
                cursor.execute(
                    "UPDATE listings SET is_active = 0 WHERE portal = ? AND is_active = 1",
                    (portal,)
                )
            
            affected = cursor.rowcount
            conn.commit()
            
            if affected > 0:
                logger.info(f"Marcados {affected} anuncios como inactivos en {portal}")
    
    def reset_new_flags(self):
        """Resetea los flags 'is_new' de todos los anuncios."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE listings SET is_new = 0 WHERE is_new = 1")
            affected = cursor.rowcount
            conn.commit()
            
            if affected > 0:
                logger.info(f"Reseteados {affected} flags de nuevos anuncios")
    
    def cleanup_old_listings(self, days: int = 90):
        """
        Elimina anuncios antiguos e inactivos.
        
        Args:
            days: Días de antigüedad para eliminar
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM listings WHERE is_active = 0 AND last_seen < ?",
                (cutoff,)
            )
            deleted = cursor.rowcount
            conn.commit()
            
            if deleted > 0:
                logger.info(f"Eliminados {deleted} anuncios antiguos (>{days} días)")
    
    # -------------------------------------------------------------------------
    # OPERACIONES DE ESTADÍSTICAS
    # -------------------------------------------------------------------------
    
    def save_run_stats(self, stats: RunStats) -> int:
        """
        Guarda las estadísticas de una ejecución.
        
        Args:
            stats: Objeto RunStats
        
        Returns:
            ID de la ejecución
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            data = stats.to_dict()
            
            if stats.id:
                # Actualizar
                columns = [k for k in data.keys() if k != 'id']
                set_clause = ", ".join([f"{col} = ?" for col in columns])
                values = [data[col] for col in columns]
                values.append(stats.id)
                
                cursor.execute(
                    f"UPDATE run_stats SET {set_clause} WHERE id = ?",
                    values
                )
            else:
                # Insertar
                del data['id']
                columns = list(data.keys())
                placeholders = ", ".join(["?" for _ in columns])
                columns_str = ", ".join(columns)
                values = [data[col] for col in columns]
                
                cursor.execute(
                    f"INSERT INTO run_stats ({columns_str}) VALUES ({placeholders})",
                    values
                )
                stats.id = cursor.lastrowid
            
            conn.commit()
            return stats.id
    
    def get_last_run(self) -> Optional[RunStats]:
        """
        Obtiene la última ejecución completada.
        
        Returns:
            Objeto RunStats o None
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM run_stats WHERE status = 'completed' ORDER BY end_time DESC LIMIT 1"
            )
            row = cursor.fetchone()
            
            if row:
                return RunStats.from_dict(dict(row))
            return None
    
    def get_run_stats(self, limit: int = 10) -> List[RunStats]:
        """
        Obtiene las últimas ejecuciones.
        
        Args:
            limit: Número máximo de resultados
        
        Returns:
            Lista de RunStats
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM run_stats ORDER BY start_time DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [RunStats.from_dict(dict(row)) for row in rows]
    
    # -------------------------------------------------------------------------
    # OPERACIONES DE EXCLUSIONES
    # -------------------------------------------------------------------------
    
    def add_exclusion(self, listing_id: str, url: str = None, reason: str = None):
        """
        Añade un anuncio a la lista de exclusiones.
        
        Args:
            listing_id: ID del anuncio
            url: URL del anuncio
            reason: Motivo de exclusión
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO exclusions (listing_id, url, reason) VALUES (?, ?, ?)",
                (listing_id, url, reason)
            )
            conn.commit()
    
    def is_excluded(self, listing_id: str) -> bool:
        """
        Verifica si un anuncio está excluido.
        
        Args:
            listing_id: ID del anuncio
        
        Returns:
            True si está excluido
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM exclusions WHERE listing_id = ?",
                (listing_id,)
            )
            return cursor.fetchone() is not None
    
    def get_exclusions(self) -> List[Dict[str, Any]]:
        """
        Obtiene todas las exclusiones.
        
        Returns:
            Lista de exclusiones
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM exclusions ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    
    # -------------------------------------------------------------------------
    # OPERACIONES DE NOTIFICACIONES
    # -------------------------------------------------------------------------
    
    def record_notification(
        self,
        listing_id: str,
        channel: str,
        status: str = "sent",
        error: str = None
    ):
        """
        Registra una notificación enviada.
        
        Args:
            listing_id: ID del anuncio
            channel: Canal (email/telegram)
            status: Estado del envío
            error: Mensaje de error si falló
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO notifications (listing_id, channel, sent_at, status, error_message)
                   VALUES (?, ?, ?, ?, ?)""",
                (listing_id, channel, datetime.now().isoformat(), status, error)
            )
            conn.commit()
    
    def was_notified(self, listing_id: str, channel: str) -> bool:
        """
        Verifica si ya se notificó un anuncio por un canal.
        
        Args:
            listing_id: ID del anuncio
            channel: Canal de notificación
        
        Returns:
            True si ya fue notificado
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM notifications WHERE listing_id = ? AND channel = ? AND status = 'sent'",
                (listing_id, channel)
            )
            return cursor.fetchone() is not None
    
    # -------------------------------------------------------------------------
    # UTILIDADES
    # -------------------------------------------------------------------------
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas generales de la base de datos.
        
        Returns:
            Diccionario con estadísticas
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Total de anuncios
            cursor.execute("SELECT COUNT(*) FROM listings")
            stats['total_listings'] = cursor.fetchone()[0]
            
            # Anuncios activos
            cursor.execute("SELECT COUNT(*) FROM listings WHERE is_active = 1")
            stats['active_listings'] = cursor.fetchone()[0]
            
            # Anuncios nuevos
            cursor.execute("SELECT COUNT(*) FROM listings WHERE is_new = 1")
            stats['new_listings'] = cursor.fetchone()[0]
            
            # Por portal
            cursor.execute(
                """SELECT portal, COUNT(*) as count, 
                          SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active
                   FROM listings GROUP BY portal"""
            )
            stats['by_portal'] = {
                row['portal']: {'total': row['count'], 'active': row['active']}
                for row in cursor.fetchall()
            }
            
            # Última ejecución
            last_run = self.get_last_run()
            if last_run:
                stats['last_run'] = {
                    'time': last_run.end_time.isoformat() if last_run.end_time else None,
                    'new_found': last_run.new_listings,
                    'status': last_run.status
                }
            
            return stats
    
    def vacuum(self):
        """Optimiza la base de datos."""
        with self.get_connection() as conn:
            conn.execute("VACUUM")
            logger.info("Base de datos optimizada")


# Instancia global para importación directa
db = DatabaseManager()
