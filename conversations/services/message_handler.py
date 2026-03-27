"""
Message Handler Service

Orchestrates the auto-reply flow:
1. Check predefined replies first
2. Try AI-powered response
3. Fall back to default message
"""
import logging
import time
from typing import Optional, Tuple
from django.utils import timezone
from django.db.models import F

from conversations.models import Conversation, Message
from replies.models import PredefinedReply
from knowledge.services import RAGService

logger = logging.getLogger(__name__)


class MessageHandler:
    """
    Handles incoming messages and generates appropriate responses.

    Priority order:
    1. Predefined replies (keyword matching)
    2. AI-generated response (from knowledge base)
    3. Fallback response (escalate to human)
    """

    def __init__(self, user):
        """
        Args:
            user: User model instance (business owner)
        """
        self.user = user
        self.rag_service = RAGService()

    def process_message(
        self,
        conversation: Conversation,
        content: str
    ) -> Message:
        """
        Process an incoming message and generate a response.

        Args:
            conversation: The conversation this message belongs to
            content: The message content from the customer

        Returns:
            The outbound Message object (response)
        """
        start_time = time.time()

        # Save the inbound message
        inbound_message = Message.objects.create(
            conversation=conversation,
            direction='inbound',
            content=content
        )

        # Try to generate a response
        response_content, response_type, confidence, predefined_reply = self._generate_response(content)

        # Calculate processing time
        processing_time = int((time.time() - start_time) * 1000)

        # Check if we should flag for human review
        needs_review = response_type == 'fallback' or (
            response_type == 'ai' and confidence < 0.5
        )


        # Create the outbound message
        outbound_message = Message.objects.create(
            conversation=conversation,
            direction='outbound',
            content=response_content,
            response_type=response_type,
            ai_confidence=confidence if response_type == 'ai' else None,
            predefined_reply=predefined_reply,
            processing_time_ms=processing_time
        )

        # Update conversation timestamp
        # Update conversation with single save operation
        # Consolidate needs_human_review update and timestamp update into one save
        conversation.needs_human_review = needs_review
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=["needs_human_review", "updated_at"])

        # Increment usage counters
        self._update_usage(response_type, predefined_reply)

        logger.info(
            f"Processed message for {self.user.email}: "
            f"type={response_type}, confidence={confidence}, "
            f"time={processing_time}ms"
        )

        return outbound_message

    def _generate_response(
        self,
        message: str
    ) -> Tuple[str, str, float, Optional[PredefinedReply]]:
        """
        Generate a response using the priority system.

        Returns:
            Tuple of (response_content, response_type, confidence, predefined_reply)
        """
        # 1. Check predefined replies first
        predefined = self._check_predefined_replies(message)
        if predefined:
            return (
                predefined.response,
                'predefined',
                1.0,  # Predefined replies have 100% confidence
                predefined
            )

        # 2. Check if user can send more replies (plan limits)
        if not self.user.can_send_reply():
            logger.warning(f"User {self.user.email} has reached plan limit")
            return (
                "Thank you for your message. We'll get back to you soon!",
                'fallback',
                0.0,
                None
            )

        # 3. Try AI-powered response
        ai_result = self.rag_service.generate_response(
            user=self.user,
            message=message
        )

        if ai_result.get('response') and ai_result.get('confidence', 0) >= 0.4:
            return (
                ai_result['response'],
                'ai',
                ai_result['confidence'],
                None
            )

        # 4. Fall back to default response
        fallback = self.rag_service.get_fallback_response(self.user)
        return (
            fallback,
            'fallback',
            ai_result.get('confidence', 0.0),
            None
        )

    def _check_predefined_replies(self, message: str) -> Optional[PredefinedReply]:
        """
        Check if any predefined reply matches the message.

        Returns the first matching reply, or None.
        """
        replies = PredefinedReply.objects.filter(
            user=self.user,
            is_active=True
        )

        for reply in replies:
            if reply.matches_message(message):
                return reply

        return None

    def _update_usage(
        self,
        response_type: str,
        predefined_reply: Optional[PredefinedReply] = None
    ):
        """
        Update usage counters atomically to prevent race conditions.
        
        Uses F() expressions for database-level atomic increments.
        """
        from accounts.models import User
        
        # Build update fields dict
        update_fields = {'monthly_replies': F('monthly_replies') + 1}
        
        if response_type == 'ai':
            update_fields['monthly_ai_replies'] = F('monthly_ai_replies') + 1
        
        # Perform atomic update at database level
        User.objects.filter(id=self.user.id).update(**update_fields)
        
        # Refresh user instance to get updated values
        # This is necessary because F() expressions don't update the in-memory object
        self.user.refresh_from_db(fields=['monthly_replies', 'monthly_ai_replies'])
        
        # Increment predefined reply usage counter atomically
        if predefined_reply:
            PredefinedReply.objects.filter(id=predefined_reply.id).update(
                use_count=F('use_count') + 1
            )


def handle_incoming_message(
    user_id: int,
    platform: str,
    customer_id: str,
    content: str,
    customer_name: str = "",
    customer_email: str = "",
    customer_phone: str = ""
) -> dict:
    """
    Convenience function to handle an incoming message.

    This is the main entry point for webhooks/integrations.

    Args:
        user_id: ID of the business owner
        platform: Platform type (email, whatsapp, instagram)
        customer_id: Platform-specific customer identifier
        content: Message content
        customer_name: Customer's name (optional)
        customer_email: Customer's email (optional)
        customer_phone: Customer's phone (optional)

    Returns:
        dict with response details
    """
    from accounts.models import User

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return {'error': 'User not found'}

    # Get or create conversation
    conversation, created = Conversation.objects.get_or_create(
        user=user,
        platform=platform,
        customer_id=customer_id,
        defaults={
            'customer_name': customer_name,
            'customer_email': customer_email,
            'customer_phone': customer_phone,
            'status': 'active'
        }
    )

    # Update customer info if provided
    if not created:
        updated = False
        if customer_name and not conversation.customer_name:
            conversation.customer_name = customer_name
            updated = True
        if customer_email and not conversation.customer_email:
            conversation.customer_email = customer_email
            updated = True
        if customer_phone and not conversation.customer_phone:
            conversation.customer_phone = customer_phone
            updated = True
        if updated:
            conversation.save()

    # Process the message
    handler = MessageHandler(user)
    response_message = handler.process_message(conversation, content)

    return {
        'conversation_id': conversation.id,
        'response': response_message.content,
        'response_type': response_message.response_type,
        'confidence': response_message.ai_confidence,
        'needs_human_review': conversation.needs_human_review,
        'processing_time_ms': response_message.processing_time_ms
    }
