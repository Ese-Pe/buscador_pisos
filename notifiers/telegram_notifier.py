"""
Notificador por Telegram para el bot inmobiliario.
Envía notificaciones de nuevos anuncios vía Telegram Bot API.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from database import Listing
from utils import LoggerMixin, format_price, format_surface, get_env, truncate_text


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
        
        # Construir mensajes
        summary_msg = self._build_summary_message(listings, profile_name)
        listing_msgs = [self._build_listing_message(l) for l in listings]
        
        if test_mode:
            self.logger.info("[TEST MODE] Mensajes que se enviarían:")
            print("\n" + "="*60)
            print("RESUMEN:")
            print(summary_msg)
            print("\nANUNCIOS:")
            for msg in listing_msgs[:3]:  # Solo primeros 3 en test
                print("-"*40)
                print(msg)
            if len(listing_msgs) > 3:
                print(f"\n... y {len(listing_msgs) - 3} anuncios más")
            print("="*60 + "\n")
            return True
        
        # Enviar mensajes
        return asyncio.run(self._send_messages_async(summary_msg, listing_msgs))
    
    async def _send_messages_async(
        self,
        summary: str,
        listing_messages: List[str]
    ) -> bool:
        """Envía los mensajes de forma asíncrona."""
        try:
            from telegram import Bot
            from telegram.error import TelegramError
            
            bot = Bot(token=self.bot_token)
            
            success = True
            
            for chat_id in self.chat_ids:
                try:
                    # Enviar resumen
                    await bot.send_message(
                        chat_id=chat_id,
                        text=summary,
                        parse_mode=self.parse_mode,
                        disable_web_page_preview=True
                    )
                    
                    # Enviar cada anuncio (con delay para evitar flood)
                    for msg in listing_messages:
                        await asyncio.sleep(0.5)  # Evitar rate limiting
                        await bot.send_message(
                            chat_id=chat_id,
                            text=msg,
                            parse_mode=self.parse_mode,
                            disable_web_page_preview=self.disable_preview
                        )
                    
                    self.logger.info(f"Notificación enviada a chat {chat_id}")
                    
                except TelegramError as e:
                    self.logger.error(f"Error enviando a chat {chat_id}: {e}")
                    success = False
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error en envío de Telegram: {e}")
            return False
    
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
    
    def _build_summary_message(self, listings: List[Listing], profile_name: str = None) -> str:
        """Construye el mensaje de resumen."""
        lines = [
            "🏠 <b>NUEVOS PISOS ENCONTRADOS</b>",
            "",
            f"📊 Total: <b>{len(listings)}</b> anuncios",
            f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        ]
        
        if profile_name:
            lines.append(f"🔍 Perfil: {profile_name}")
        
        # Resumen por portal
        portals = {}
        for l in listings:
            portals[l.portal] = portals.get(l.portal, 0) + 1
        
        if portals:
            lines.append("")
            lines.append("📱 Por portal:")
            for portal, count in sorted(portals.items(), key=lambda x: -x[1]):
                lines.append(f"  • {portal}: {count}")
        
        # Rango de precios
        prices = [l.price for l in listings if l.price]
        if prices:
            lines.append("")
            lines.append(f"💰 Precios: {format_price(min(prices))} - {format_price(max(prices))}")
        
        return "\n".join(lines)
    
    def _build_listing_message(self, listing: Listing) -> str:
        """Construye el mensaje para un anuncio individual."""
        lines = []
        
        # Título
        title = truncate_text(listing.title or "Sin título", 100)
        lines.append(f"🏢 <b>{self._escape_html(title)}</b>")
        
        # Precio
        if listing.price:
            lines.append(f"💰 <b>{format_price(listing.price)}</b>")
        else:
            lines.append("💰 Consultar precio")
        
        # Ubicación
        location = listing.get_location_string()
        lines.append(f"📍 {self._escape_html(location)}")
        
        # Características principales
        features = []
        if listing.bedrooms:
            features.append(f"🛏 {listing.bedrooms} hab")
        if listing.bathrooms:
            features.append(f"🚿 {listing.bathrooms} baños")
        if listing.surface:
            features.append(f"📐 {listing.surface} m²")
        if listing.floor:
            features.append(f"🏢 Planta {listing.floor}")
        
        if features:
            lines.append(" | ".join(features))
        
        # Extras
        extras = []
        if listing.has_elevator:
            extras.append("Ascensor")
        if listing.has_parking:
            extras.append("Garaje")
        if listing.has_pool:
            extras.append("Piscina")
        if listing.has_terrace:
            extras.append("Terraza")
        if listing.has_ac:
            extras.append("A/A")
        if listing.has_storage:
            extras.append("Trastero")
        
        if extras:
            lines.append(f"✨ {', '.join(extras)}")
        
        # Descripción breve
        if listing.description:
            desc = truncate_text(listing.description, 150)
            lines.append(f"\n📝 {self._escape_html(desc)}")
        
        # Portal y link
        lines.append("")
        lines.append(f"🔗 <a href=\"{listing.url}\">Ver en {listing.portal}</a>")
        
        return "\n".join(lines)
    
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
