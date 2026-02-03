"""
Notificador por Telegram para el bot inmobiliario.
Envía notificaciones de nuevos anuncios vía Telegram Bot API.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import Listing
from utils import LoggerMixin, format_price, format_surface, get_env, truncate_text
import os


class TelegramNotifier(LoggerMixin):
    """
    Notificador por Telegram usando la Bot API.
    
    Requiere un bot creado con @BotFather y los chat_ids de los destinatarios.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Inicializa el notificador de Telegram.
        
        Args:
            config: Configuración del bot
        """
        self.config = config or {}
        
        # Token del bot
        self.bot_token = self.config.get('bot_token') or get_env('TELEGRAM_BOT_TOKEN')
        
        # Chat IDs
        chat_ids = self.config.get('chat_ids') or get_env('TELEGRAM_CHAT_IDS', '')
        if isinstance(chat_ids, str):
            self.chat_ids = [cid.strip() for cid in chat_ids.split(',') if cid.strip()]
        else:
            self.chat_ids = list(chat_ids) if chat_ids else []
        
        # Configuración de mensajes
        self.parse_mode = self.config.get('parse_mode', 'HTML')
        self.disable_preview = self.config.get('disable_web_page_preview', False)
        
        self.enabled = self.config.get('enabled', True)
        self._bot = None
        
        self.logger.info(f"TelegramNotifier inicializado (enabled={self.enabled})")
    
    def is_configured(self) -> bool:
        """
        Verifica si el notificador está correctamente configurado.
        
        Returns:
            True si tiene toda la configuración necesaria
        """
        return bool(self.enabled and self.bot_token and self.chat_ids)
    
    def _get_bot(self):
        """Obtiene o crea la instancia del bot."""
        if self._bot is None:
            try:
                from telegram import Bot
                self._bot = Bot(token=self.bot_token)
            except ImportError:
                self.logger.error("python-telegram-bot no está instalado. "
                                 "Ejecuta: pip install python-telegram-bot")
                raise
        return self._bot
    
    def send_notification(
        self,
        listings: List[Listing],
        profile_name: str = None,
        test_mode: bool = False
    ) -> bool:
        """
        Envía notificaciones de nuevos anuncios.

        Envía un mensaje de resumen con link al dashboard en lugar de
        mensajes individuales para cada anuncio.

        Args:
            listings: Lista de anuncios nuevos
            profile_name: Nombre del perfil de búsqueda
            test_mode: Si es True, solo imprime sin enviar

        Returns:
            True si se envió correctamente
        """
        if not listings:
            self.logger.info("No hay anuncios nuevos para notificar")
            return True

        if not self.is_configured():
            self.logger.warning("TelegramNotifier no está configurado correctamente")
            return False

        # Construir mensaje de resumen/recordatorio
        reminder_msg = self._build_reminder_message(listings, profile_name)

        if test_mode:
            self.logger.info("[TEST MODE] Mensaje que se enviaría:")
            print("\n" + "="*60)
            print(reminder_msg)
            print("="*60 + "\n")
            return True

        # Enviar solo el mensaje de resumen
        return asyncio.run(self._send_reminder_async(reminder_msg))
    
    async def _send_reminder_async(self, message: str) -> bool:
        """Envía el mensaje de recordatorio de forma asíncrona."""
        try:
            from telegram import Bot
            from telegram.error import TelegramError

            bot = Bot(token=self.bot_token)
            success = True

            for chat_id in self.chat_ids:
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode=self.parse_mode,
                        disable_web_page_preview=False
                    )
                    self.logger.info(f"Recordatorio enviado a chat {chat_id}")

                except TelegramError as e:
                    self.logger.error(f"Error enviando a chat {chat_id}: {e}")
                    success = False

            return success

        except Exception as e:
            self.logger.error(f"Error en envío de Telegram: {e}")
            return False

    def _build_reminder_message(self, listings: List[Listing], profile_name: str = None) -> str:
        """Construye el mensaje de recordatorio con resumen y link al dashboard."""
        # Get dashboard URL from environment
        dashboard_url = os.environ.get('RENDER_SERVICE_URL', '')

        lines = [
            "🏠 <b>Nuevos pisos encontrados</b>",
            "",
            f"Se han encontrado <b>{len(listings)}</b> nuevos anuncios.",
            "",
        ]

        # Resumen por portal
        portals = {}
        for l in listings:
            portals[l.portal] = portals.get(l.portal, 0) + 1

        if portals:
            lines.append("📱 <b>Por portal:</b>")
            for portal, count in sorted(portals.items(), key=lambda x: -x[1]):
                lines.append(f"  • {portal.title()}: {count}")
            lines.append("")

        # Rango de precios
        prices = [l.price for l in listings if l.price]
        if prices:
            lines.append(f"💰 Precios: {format_price(min(prices))} - {format_price(max(prices))}")
            lines.append("")

        # Link al dashboard
        if dashboard_url:
            lines.append(f"👉 <a href=\"{dashboard_url}/listings\">Ver todos en el Dashboard</a>")
        else:
            lines.append("📋 Revisa el dashboard para más detalles")

        lines.append("")
        lines.append(f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        return "\n".join(lines)
    
    def send_single_listing(self, listing: Listing, test_mode: bool = False) -> bool:
        """
        Envía una notificación de un único anuncio.

        Args:
            listing: Anuncio a notificar
            test_mode: Modo de prueba

        Returns:
            True si se envió correctamente
        """
        return self.send_notification([listing], test_mode=test_mode)

    def _escape_html(self, text: str) -> str:
        """Escapa caracteres especiales de HTML."""
        if not text:
            return ""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'))
    
    async def test_connection_async(self) -> bool:
        """Prueba la conexión con Telegram de forma asíncrona."""
        try:
            from telegram import Bot
            
            bot = Bot(token=self.bot_token)
            me = await bot.get_me()
            self.logger.info(f"Bot conectado: @{me.username}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error conectando a Telegram: {e}")
            return False
    
    def test_connection(self) -> bool:
        """
        Prueba la conexión con Telegram.
        
        Returns:
            True si la conexión es exitosa
        """
        if not self.bot_token:
            self.logger.error("Token de bot no configurado")
            return False
        
        return asyncio.run(self.test_connection_async())
    
    def send_test_message(self) -> bool:
        """
        Envía un mensaje de prueba.
        
        Returns:
            True si se envió correctamente
        """
        if not self.is_configured():
            self.logger.error("TelegramNotifier no está configurado")
            return False
        
        test_message = (
            "🤖 <b>Test de Real Estate Bot</b>\n\n"
            "✅ La conexión con Telegram funciona correctamente.\n"
            f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )
        
        async def send():
            from telegram import Bot
            bot = Bot(token=self.bot_token)
            
            for chat_id in self.chat_ids:
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=test_message,
                        parse_mode='HTML'
                    )
                    self.logger.info(f"Mensaje de prueba enviado a {chat_id}")
                except Exception as e:
                    self.logger.error(f"Error enviando a {chat_id}: {e}")
                    return False
            return True
        
        return asyncio.run(send())
