"""
Notificador por email para el bot inmobiliario.
Envía resúmenes de nuevos anuncios vía SMTP.
"""

import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from database import Listing
from utils import LoggerMixin, format_price, format_surface, get_env


class EmailNotifier(LoggerMixin):
    """
    Notificador por email usando SMTP.
    
    Soporta Gmail, Outlook y otros proveedores SMTP.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Inicializa el notificador de email.
        
        Args:
            config: Configuración del email
        """
        self.config = config or {}
        
        # Configuración SMTP
        self.smtp_server = self.config.get('smtp_server', 'smtp.gmail.com')
        self.smtp_port = self.config.get('smtp_port', 587)
        self.use_tls = self.config.get('use_tls', True)
        
        # Credenciales
        self.username = self.config.get('username') or get_env('SMTP_USERNAME')
        self.password = self.config.get('password') or get_env('SMTP_PASSWORD')
        
        # Direcciones
        self.from_address = self.config.get('from_address', self.username)
        self.to_addresses = self.config.get('to_addresses', [])
        
        if isinstance(self.to_addresses, str):
            self.to_addresses = [addr.strip() for addr in self.to_addresses.split(',')]
        
        # Template del asunto
        self.subject_template = self.config.get(
            'subject_template',
            "🏠 {count} nuevos pisos encontrados - {date}"
        )
        
        self.enabled = self.config.get('enabled', True)
        
        self.logger.info(f"EmailNotifier inicializado (enabled={self.enabled})")
    
    def is_configured(self) -> bool:
        """
        Verifica si el notificador está correctamente configurado.
        
        Returns:
            True si tiene toda la configuración necesaria
        """
        return bool(
            self.enabled and
            self.username and
            self.password and
            self.to_addresses
        )
    
    def send_notification(
        self,
        listings: List[Listing],
        profile_name: str = None,
        test_mode: bool = False
    ) -> bool:
        """
        Envía una notificación con los nuevos anuncios.
        
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
            self.logger.warning("EmailNotifier no está configurado correctamente")
            return False
        
        # Construir mensaje
        subject = self.subject_template.format(
            count=len(listings),
            date=datetime.now().strftime('%d/%m/%Y'),
            profile=profile_name or 'General'
        )
        
        html_body = self._build_html_body(listings, profile_name)
        text_body = self._build_text_body(listings, profile_name)
        
        if test_mode:
            self.logger.info(f"[TEST MODE] Email que se enviaría:")
            self.logger.info(f"  Asunto: {subject}")
            self.logger.info(f"  Destinatarios: {self.to_addresses}")
            self.logger.info(f"  Anuncios: {len(listings)}")
            print("\n" + "="*60)
            print(f"ASUNTO: {subject}")
            print("="*60)
            print(text_body)
            print("="*60 + "\n")
            return True
        
        # Crear mensaje MIME
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.from_address
        msg['To'] = ', '.join(self.to_addresses)
        
        # Añadir partes (texto y HTML)
        part1 = MIMEText(text_body, 'plain', 'utf-8')
        part2 = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(part1)
        msg.attach(part2)
        
        # Enviar
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.sendmail(
                    self.from_address,
                    self.to_addresses,
                    msg.as_string()
                )
            
            self.logger.info(f"Email enviado correctamente a {len(self.to_addresses)} destinatarios")
            return True
            
        except smtplib.SMTPAuthenticationError:
            self.logger.error("Error de autenticación SMTP. Verifica usuario y contraseña.")
            return False
        except smtplib.SMTPException as e:
            self.logger.error(f"Error SMTP: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error enviando email: {e}")
            return False
    
    def _build_html_body(self, listings: List[Listing], profile_name: str = None) -> str:
        """Construye el cuerpo HTML del email."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background: #2c3e50; color: white; padding: 20px; text-align: center; }}
                .listing {{ border: 1px solid #ddd; margin: 15px 0; padding: 15px; border-radius: 8px; }}
                .listing:hover {{ box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
                .price {{ font-size: 24px; color: #27ae60; font-weight: bold; }}
                .location {{ color: #7f8c8d; margin: 5px 0; }}
                .features {{ display: flex; gap: 15px; margin: 10px 0; }}
                .feature {{ background: #ecf0f1; padding: 5px 10px; border-radius: 4px; }}
                .link {{ display: inline-block; background: #3498db; color: white; 
                         padding: 10px 20px; text-decoration: none; border-radius: 5px; }}
                .link:hover {{ background: #2980b9; }}
                .footer {{ text-align: center; padding: 20px; color: #7f8c8d; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🏠 {len(listings)} Nuevos Pisos Encontrados</h1>
                {f'<p>Perfil: {profile_name}</p>' if profile_name else ''}
                <p>{datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
            </div>
        """
        
        for listing in listings:
            features_html = ""
            if listing.bedrooms:
                features_html += f'<span class="feature">🛏 {listing.bedrooms} hab.</span>'
            if listing.bathrooms:
                features_html += f'<span class="feature">🚿 {listing.bathrooms} baños</span>'
            if listing.surface:
                features_html += f'<span class="feature">📐 {listing.surface} m²</span>'
            if listing.floor:
                features_html += f'<span class="feature">🏢 {listing.floor}</span>'
            
            extra_features = []
            if listing.has_elevator:
                extra_features.append("Ascensor")
            if listing.has_parking:
                extra_features.append("Garaje")
            if listing.has_pool:
                extra_features.append("Piscina")
            if listing.has_terrace:
                extra_features.append("Terraza")
            if listing.has_ac:
                extra_features.append("A/A")
            
            html += f"""
            <div class="listing">
                <h2>{listing.title or 'Sin título'}</h2>
                <p class="price">{format_price(listing.price) if listing.price else 'Consultar precio'}</p>
                <p class="location">📍 {listing.get_location_string()}</p>
                <div class="features">{features_html}</div>
                {f'<p>✨ {", ".join(extra_features)}</p>' if extra_features else ''}
                {f'<p>{listing.description[:200]}...</p>' if listing.description else ''}
                <p><a class="link" href="{listing.url}" target="_blank">Ver anuncio →</a></p>
                <small>Portal: {listing.portal}</small>
            </div>
            """
        
        html += """
            <div class="footer">
                <p>Este email fue generado automáticamente por Real Estate Bot</p>
                <p>Para dejar de recibir notificaciones, modifica la configuración del bot</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _build_text_body(self, listings: List[Listing], profile_name: str = None) -> str:
        """Construye el cuerpo de texto plano del email."""
        lines = [
            f"🏠 {len(listings)} NUEVOS PISOS ENCONTRADOS",
            f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        ]
        
        if profile_name:
            lines.append(f"Perfil: {profile_name}")
        
        lines.append("")
        lines.append("=" * 50)
        
        for i, listing in enumerate(listings, 1):
            lines.append(f"\n[{i}] {listing.title or 'Sin título'}")
            lines.append(f"    💰 {format_price(listing.price) if listing.price else 'Consultar'}")
            lines.append(f"    📍 {listing.get_location_string()}")
            
            features = []
            if listing.bedrooms:
                features.append(f"{listing.bedrooms} hab.")
            if listing.bathrooms:
                features.append(f"{listing.bathrooms} baños")
            if listing.surface:
                features.append(f"{listing.surface} m²")
            if features:
                lines.append(f"    🏠 {' | '.join(features)}")
            
            extras = []
            if listing.has_elevator:
                extras.append("Ascensor")
            if listing.has_parking:
                extras.append("Garaje")
            if listing.has_pool:
                extras.append("Piscina")
            if extras:
                lines.append(f"    ✨ {', '.join(extras)}")
            
            lines.append(f"    🔗 {listing.url}")
            lines.append(f"    Portal: {listing.portal}")
            lines.append("-" * 50)
        
        lines.append("\n---")
        lines.append("Email generado automáticamente por Real Estate Bot")
        
        return "\n".join(lines)
    
    def test_connection(self) -> bool:
        """
        Prueba la conexión SMTP.
        
        Returns:
            True si la conexión es exitosa
        """
        if not self.username or not self.password:
            self.logger.error("Credenciales SMTP no configuradas")
            return False
        
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
            
            self.logger.info("Conexión SMTP exitosa")
            return True
            
        except Exception as e:
            self.logger.error(f"Error conectando a SMTP: {e}")
            return False
