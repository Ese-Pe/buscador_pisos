"""
Módulo de logging para el bot inmobiliario.
Configura logging con rotación de archivos y salida a consola.
"""

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Formatter con colores para la salida de consola."""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Verde
        'WARNING': '\033[33m',    # Amarillo
        'ERROR': '\033[31m',      # Rojo
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logger(
    name: str = "real_estate_bot",
    log_dir: str = "logs",
    level: str = "INFO",
    log_to_file: bool = True,
    log_to_console: bool = True,
    max_file_size_mb: int = 10,
    backup_count: int = 5
) -> logging.Logger:
    """
    Configura y devuelve un logger con las opciones especificadas.
    
    Args:
        name: Nombre del logger
        log_dir: Directorio para archivos de log
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Si guardar logs en archivo
        log_to_console: Si mostrar logs en consola
        max_file_size_mb: Tamaño máximo de archivo antes de rotar
        backup_count: Número de archivos de backup a mantener
    
    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    
    # Evitar duplicación de handlers si ya está configurado
    if logger.handlers:
        return logger
    
    # Establecer nivel
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Formato de log
    file_format = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(module)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_format = ColoredFormatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Handler de consola
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)
    
    # Handler de archivo
    if log_to_file:
        # Crear directorio si no existe
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # Nombre del archivo con fecha
        log_filename = log_path / f"bot_{datetime.now().strftime('%Y%m%d')}.log"
        
        # Rotating file handler
        file_handler = RotatingFileHandler(
            log_filename,
            maxBytes=max_file_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Obtiene un logger existente o crea uno nuevo.
    
    Args:
        name: Nombre del logger. Si es None, usa el logger raíz del bot.
    
    Returns:
        Logger
    """
    if name:
        return logging.getLogger(f"real_estate_bot.{name}")
    return logging.getLogger("real_estate_bot")


class LoggerMixin:
    """
    Mixin para añadir capacidades de logging a cualquier clase.
    
    Uso:
        class MiClase(LoggerMixin):
            def mi_metodo(self):
                self.logger.info("Mensaje de log")
    """
    
    @property
    def logger(self) -> logging.Logger:
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger


# Crear logger global para importación directa
logger = get_logger()
