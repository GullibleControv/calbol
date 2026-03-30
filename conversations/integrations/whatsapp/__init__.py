"""
WhatsApp Business API Integration

Provides:
- Webhook receiver for incoming WhatsApp messages
- Message sender via WhatsApp Cloud API
- High-level processor for auto-replies
"""

from .receiver import WhatsAppWebhookHandler, InboundWhatsAppMessage
from .sender import WhatsAppSender, send_whatsapp_message
from .processor import WhatsAppProcessor, setup_whatsapp_platform

__all__ = [
    'WhatsAppWebhookHandler',
    'InboundWhatsAppMessage',
    'WhatsAppSender',
    'send_whatsapp_message',
    'WhatsAppProcessor',
    'setup_whatsapp_platform',
]
