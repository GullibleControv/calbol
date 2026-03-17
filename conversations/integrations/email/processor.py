"""
Email Processor

High-level email processing logic for the CalBol platform.
"""
import logging
from typing import Optional
from django.db import transaction

from conversations.models import Platform, Conversation, Message
from conversations.services import MessageHandler
from .sender import EmailSender
from .receiver import InboundEmail

logger = logging.getLogger(__name__)


class EmailProcessor:
    """
    Process emails for a specific platform/user.

    Usage:
        processor = EmailProcessor(platform)
        result = processor.process_inbound(email)
    """

    def __init__(self, platform: Platform):
        """
        Initialize processor for a platform.

        Args:
            platform: Platform model instance (must be email type)
        """
        if platform.platform_type != 'email':
            raise ValueError("Platform must be email type")

        self.platform = platform
        self.user = platform.user
        self.sender = EmailSender()
        self.credentials = platform.credentials or {}

    def process_inbound(self, email: InboundEmail) -> dict:
        """
        Process an inbound email.

        1. Get or create conversation
        2. Save inbound message
        3. Generate AI response
        4. Save outbound message
        5. Send reply email

        Args:
            email: Parsed InboundEmail object

        Returns:
            dict with processing result
        """
        logger.info(f"Processing email from {email.from_email}")

        try:
            with transaction.atomic():
                # Get or create conversation
                conversation = self._get_or_create_conversation(email)

                # Process through message handler
                handler = MessageHandler(self.user)
                response_message = handler.process_message(
                    conversation=conversation,
                    content=email.body_plain
                )

                # Send reply email
                send_result = self._send_reply(email, response_message.content)

                return {
                    'success': True,
                    'conversation_id': conversation.id,
                    'message_id': response_message.id,
                    'response_type': response_message.response_type,
                    'confidence': response_message.ai_confidence,
                    'needs_review': conversation.needs_human_review,
                    'email_sent': send_result.get('success', False),
                }

        except Exception as e:
            logger.error(f"Error processing email: {e}")
            return {
                'success': False,
                'error': str(e),
            }

    def _get_or_create_conversation(self, email: InboundEmail) -> Conversation:
        """Get existing conversation or create new one."""

        conversation, created = Conversation.objects.get_or_create(
            user=self.user,
            platform='email',
            customer_id=email.from_email,
            defaults={
                'customer_name': email.from_name or '',
                'customer_email': email.from_email,
                'status': 'active',
            }
        )

        if created:
            logger.info(f"Created new conversation for {email.from_email}")
        else:
            # Update customer name if we have it now
            if email.from_name and not conversation.customer_name:
                conversation.customer_name = email.from_name
                conversation.save(update_fields=['customer_name'])

        return conversation

    def _send_reply(self, original_email: InboundEmail, response: str) -> dict:
        """Send reply email to customer."""

        from_email = self.credentials.get('from_email')
        from_name = self.credentials.get('from_name', 'Support')

        if not from_email:
            logger.warning("No from_email configured, skipping send")
            return {'success': False, 'error': 'from_email not configured'}

        return self.sender.send_reply(
            to=original_email.from_email,
            subject=original_email.subject,
            body=response,
            from_email=from_email,
            from_name=from_name,
        )

    def send_manual_reply(
        self,
        conversation: Conversation,
        content: str,
        subject: Optional[str] = None,
    ) -> dict:
        """
        Send a manual reply to a conversation.

        Args:
            conversation: The conversation to reply to
            content: Reply content
            subject: Email subject (optional)

        Returns:
            dict with send result
        """
        if not conversation.customer_email:
            return {'success': False, 'error': 'No customer email'}

        from_email = self.credentials.get('from_email')
        from_name = self.credentials.get('from_name', 'Support')

        if not from_email:
            return {'success': False, 'error': 'from_email not configured'}

        # Get last subject from conversation or use default
        if not subject:
            last_message = conversation.messages.filter(
                direction='inbound'
            ).last()
            subject = "Your inquiry"

        result = self.sender.send_reply(
            to=conversation.customer_email,
            subject=subject,
            body=content,
            from_email=from_email,
            from_name=from_name,
        )

        if result.get('success'):
            # Save the outbound message
            Message.objects.create(
                conversation=conversation,
                direction='outbound',
                content=content,
                response_type='manual',
            )

        return result


def setup_email_platform(
    user,
    from_email: str,
    from_name: str = "Support",
) -> Platform:
    """
    Set up email platform for a user.

    Args:
        user: User model instance
        from_email: Email address to send from (must be verified with Resend)
        from_name: Display name for sender

    Returns:
        Platform instance
    """
    platform, created = Platform.objects.update_or_create(
        user=user,
        platform_type='email',
        defaults={
            'is_active': True,
            'credentials': {
                'from_email': from_email,
                'from_name': from_name,
            }
        }
    )

    if created:
        logger.info(f"Created email platform for {user.email}")
    else:
        logger.info(f"Updated email platform for {user.email}")

    return platform
