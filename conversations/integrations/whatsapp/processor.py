"""
WhatsApp Processor

High-level WhatsApp processing logic for the CalBol platform.
Handles:
- Inbound message processing with AI/predefined responses
- Conversation management
- Manual replies
"""
import logging
from typing import Optional
from django.db import transaction

from conversations.models import Platform, Conversation, Message
from conversations.services import MessageHandler
from .sender import WhatsAppSender
from .receiver import InboundWhatsAppMessage

logger = logging.getLogger(__name__)


class WhatsAppProcessor:
    """
    Process WhatsApp messages for a specific platform/user.

    Usage:
        processor = WhatsAppProcessor(platform)
        result = processor.process_inbound(message)
    """

    def __init__(self, platform: Platform):
        """
        Initialize processor for a platform.

        Args:
            platform: Platform model instance (must be whatsapp type)
        """
        if platform.platform_type != 'whatsapp':
            raise ValueError("Platform must be whatsapp type")

        self.platform = platform
        self.user = platform.user
        self.credentials = platform.credentials or {}

        # Initialize sender with platform credentials
        self.sender = WhatsAppSender(
            phone_number_id=self.credentials.get('phone_number_id'),
            access_token=self.credentials.get('access_token')
        )

    def process_inbound(self, message: InboundWhatsAppMessage) -> dict:
        """
        Process an inbound WhatsApp message.

        1. Mark message as read
        2. Get or create conversation
        3. Generate AI/predefined response
        4. Send reply via WhatsApp
        5. Save messages

        Args:
            message: Parsed InboundWhatsAppMessage object

        Returns:
            dict with processing result
        """
        logger.info(f"Processing WhatsApp message from {message.from_number}")

        try:
            with transaction.atomic():
                # Get or create conversation
                conversation = self._get_or_create_conversation(message)

                # Get message content to process
                content = message.get_display_content()

                # Process through message handler
                handler = MessageHandler(self.user)
                response_message = handler.process_message(
                    conversation=conversation,
                    content=content
                )

                # Mark incoming message as read
                self.sender.mark_as_read(message_id=message.message_id)

                # Send reply
                send_result = self.sender.send_text(
                    to=message.from_number,
                    message=response_message.content
                )

                return {
                    'success': True,
                    'conversation_id': conversation.id,
                    'message_id': response_message.id,
                    'response_type': response_message.response_type,
                    'confidence': response_message.ai_confidence,
                    'needs_review': conversation.needs_human_review,
                    'whatsapp_sent': send_result.get('success', False),
                    'whatsapp_message_id': send_result.get('message_id'),
                }

        except Exception as e:
            logger.error(f"Error processing WhatsApp message: {e}")
            return {
                'success': False,
                'error': str(e),
            }

    def _get_or_create_conversation(
        self, message: InboundWhatsAppMessage
    ) -> Conversation:
        """Get existing conversation or create new one."""

        conversation, created = Conversation.objects.get_or_create(
            user=self.user,
            platform='whatsapp',
            customer_id=message.from_number,
            defaults={
                'customer_name': message.from_name or '',
                'status': 'active',
            }
        )

        if created:
            logger.info(f"Created new WhatsApp conversation for {message.from_number}")
        else:
            # Update customer name if we have it now
            if message.from_name and not conversation.customer_name:
                conversation.customer_name = message.from_name
                conversation.save(update_fields=['customer_name'])

        return conversation

    def send_manual_reply(
        self,
        conversation: Conversation,
        content: str,
    ) -> dict:
        """
        Send a manual reply to a conversation.

        Args:
            conversation: The conversation to reply to
            content: Reply content

        Returns:
            dict with send result
        """
        if not conversation.customer_id:
            return {'success': False, 'error': 'No customer phone number'}

        # Send via WhatsApp
        result = self.sender.send_text(
            to=conversation.customer_id,
            message=content
        )

        if result.get('success'):
            # Save the outbound message
            Message.objects.create(
                conversation=conversation,
                direction='outbound',
                content=content,
                response_type='manual',
            )
            logger.info(f"Manual reply sent to {conversation.customer_id}")

        return result

    def send_template(
        self,
        conversation: Conversation,
        template_name: str,
        language: str = "en",
        components: Optional[list] = None
    ) -> dict:
        """
        Send a template message to a conversation.

        Args:
            conversation: The conversation to send to
            template_name: WhatsApp approved template name
            language: Template language
            components: Template components

        Returns:
            dict with send result
        """
        if not conversation.customer_id:
            return {'success': False, 'error': 'No customer phone number'}

        result = self.sender.send_template(
            to=conversation.customer_id,
            template_name=template_name,
            language=language,
            components=components
        )

        if result.get('success'):
            Message.objects.create(
                conversation=conversation,
                direction='outbound',
                content=f"[Template: {template_name}]",
                response_type='manual',
            )

        return result


def setup_whatsapp_platform(
    user,
    phone_number_id: str,
    display_phone_number: str,
    access_token: str,
    business_account_id: Optional[str] = None
) -> Platform:
    """
    Set up WhatsApp platform for a user.

    Args:
        user: User model instance
        phone_number_id: WhatsApp phone number ID from Meta dashboard
        display_phone_number: Display phone number (e.g., +15551234567)
        access_token: Access token for API authentication
        business_account_id: Optional WhatsApp Business Account ID

    Returns:
        Platform instance
    """
    credentials = {
        'phone_number_id': phone_number_id,
        'display_phone_number': display_phone_number,
        'access_token': access_token,
    }

    if business_account_id:
        credentials['business_account_id'] = business_account_id

    platform, created = Platform.objects.update_or_create(
        user=user,
        platform_type='whatsapp',
        defaults={
            'is_active': True,
            'credentials': credentials
        }
    )

    if created:
        logger.info(f"Created WhatsApp platform for {user.email}")
    else:
        logger.info(f"Updated WhatsApp platform for {user.email}")

    return platform
