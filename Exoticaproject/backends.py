import os
import logging
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import sanitize_address
from mailjet_rest import Client

logger = logging.getLogger(__name__)

class MailjetBackend(BaseEmailBackend):
    """
    Backend personalizado para enviar emails usando Mailjet API
    """
    
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        
        # Obtener las credenciales de Mailjet desde variables de entorno
        self.api_key = os.environ.get('MJ_APIKEY_PUBLIC')
        self.api_secret = os.environ.get('MJ_APIKEY_PRIVATE')
        
        if not self.api_key or not self.api_secret:
            if not self.fail_silently:
                raise ValueError("Las variables de entorno MJ_APIKEY_PUBLIC y MJ_APIKEY_PRIVATE deben estar definidas")
            logger.error("Credenciales de Mailjet no encontradas en variables de entorno")
            return
            
        # Inicializar el cliente de Mailjet
        self.mailjet = Client(auth=(self.api_key, self.api_secret), version='v3.1')
    
    def send_messages(self, email_messages):
        """
        Envía una lista de mensajes de email usando Mailjet API
        """
        if not email_messages:
            return 0
            
        if not hasattr(self, 'mailjet') or not self.mailjet:
            if not self.fail_silently:
                raise ValueError("Cliente de Mailjet no inicializado")
            return 0
        
        num_sent = 0
        
        for message in email_messages:
            try:
                if self._send_message(message):
                    num_sent += 1
            except Exception as e:
                logger.error(f"Error enviando email: {str(e)}")
                if not self.fail_silently:
                    raise
                    
        return num_sent
    
    def _send_message(self, message):
        """
        Envía un mensaje individual usando Mailjet API
        """
        try:
            # Preparar los destinatarios
            to_recipients = []
            for email in message.to:
                name, addr = sanitize_address(email, message.encoding)
                to_recipients.append({
                    "Email": addr,
                    "Name": name if name != addr else ""
                })
            
            # Preparar CC si existe
            cc_recipients = []
            if hasattr(message, 'cc') and message.cc:
                for email in message.cc:
                    name, addr = sanitize_address(email, message.encoding)
                    cc_recipients.append({
                        "Email": addr,
                        "Name": name if name != addr else ""
                    })
            
            # Preparar BCC si existe
            bcc_recipients = []
            if hasattr(message, 'bcc') and message.bcc:
                for email in message.bcc:
                    name, addr = sanitize_address(email, message.encoding)
                    bcc_recipients.append({
                        "Email": addr,
                        "Name": name if name != addr else ""
                    })
            
            # Preparar el remitente
            from_name, from_addr = sanitize_address(message.from_email, message.encoding)
            
            # Construir el mensaje para Mailjet
            mailjet_message = {
                "From": {
                    "Email": from_addr,
                    "Name": from_name if from_name != from_addr else "L&M Exotic Fruit"
                },
                "To": to_recipients,
                "Subject": message.subject,
            }
            
            # Añadir CC y BCC si existen
            if cc_recipients:
                mailjet_message["Cc"] = cc_recipients
            if bcc_recipients:
                mailjet_message["Bcc"] = bcc_recipients
            
            # Determinar si el mensaje es HTML o texto plano
            if message.content_subtype == 'html':
                mailjet_message["HTMLPart"] = message.body
            else:
                mailjet_message["TextPart"] = message.body
            
            # Manejar adjuntos si existen
            if hasattr(message, 'attachments') and message.attachments:
                attachments = []
                for attachment in message.attachments:
                    if hasattr(attachment, 'get_content'):
                        # Django EmailMessage attachment
                        content = attachment.get_content()
                        filename = attachment.get_filename()
                        content_type = attachment.get_content_type()
                    else:
                        # Tuple format (filename, content, mimetype)
                        filename, content, content_type = attachment
                    
                    # Convertir contenido a base64 si es necesario
                    if isinstance(content, bytes):
                        import base64
                        content_b64 = base64.b64encode(content).decode('utf-8')
                    else:
                        import base64
                        content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
                    
                    attachments.append({
                        "ContentType": content_type,
                        "Filename": filename,
                        "Base64Content": content_b64
                    })
                
                if attachments:
                    mailjet_message["Attachments"] = attachments
            
            # Preparar los datos para la API de Mailjet
            data = {
                'Messages': [mailjet_message]
            }
            
            # Enviar el mensaje
            result = self.mailjet.send.create(data=data)
            
            # Verificar el resultado
            if result.status_code == 200:
                response_data = result.json()
                if response_data.get('Messages') and len(response_data['Messages']) > 0:
                    message_status = response_data['Messages'][0].get('Status')
                    if message_status == 'success':
                        logger.info(f"Email enviado exitosamente a {[r['Email'] for r in to_recipients]}")
                        return True
                    else:
                        logger.error(f"Error en el envío: {message_status}")
                        return False
                else:
                    logger.error("Respuesta inesperada de Mailjet")
                    return False
            else:
                logger.error(f"Error HTTP {result.status_code}: {result.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error enviando mensaje: {str(e)}")
            if not self.fail_silently:
                raise
            return False