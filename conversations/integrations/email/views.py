"""
Email Webhook Views

Endpoints for receiving inbound emails from email service providers.
"""
import logging
import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views import View
from django.utils.decorators import method_decorator

from conversations.models import Platform
from conversations.services import handle_incoming_message
from .receiver import EmailWebhookHandler, InboundEmail
from .sender import EmailSender

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class EmailWebhookView(View):
    """
    Universal email webhook endpoint.

    Handles inbound emails from:
    - SendGrid (Inbound Parse)
    - Mailgun (Routes)
    - Postmark (Inbound)

    URL: /api/v1/webhooks/email/<provider>/<platform_id>/
    """

    def post(self, request, provider: str, platform_id: str):
        """Handle incoming email webhook."""

        logger.info(f"Received email webhook: provider={provider}, platform={platform_id}")

        # Get the platform configuration
        try:
            platform = Platform.objects.get(
                id=platform_id,
                platform_type='email',
                is_active=True
            )
        except Platform.DoesNotExist:
            logger.warning(f"Platform not found or inactive: {platform_id}")
            return JsonResponse({'error': 'Platform not found'}, status=404)

        # Parse the incoming email based on provider
        handler = EmailWebhookHandler()

        if provider == 'sendgrid':
            email = handler.parse_sendgrid(request.POST.dict())
        elif provider == 'mailgun':
            email = handler.parse_mailgun(request.POST.dict())
        elif provider == 'postmark':
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                data = request.POST.dict()
            email = handler.parse_postmark(data)
        else:
            # Try generic parsing
            email = handler.parse_generic(request.POST.dict())

        if not email:
            logger.error("Failed to parse incoming email")
            return JsonResponse({'error': 'Failed to parse email'}, status=400)

        # Process the email through our message handler
        result = self._process_email(platform, email)

        return JsonResponse(result)

    def _process_email(self, platform: Platform, email: InboundEmail) -> dict:
        """
        Process incoming email and generate response.

        Args:
            platform: The Platform model instance
            email: Parsed InboundEmail

        Returns:
            dict with processing result
        """
        # Use email address as customer_id for email platform
        customer_id = email.from_email

        # Handle the incoming message
        result = handle_incoming_message(
            user_id=platform.user_id,
            platform='email',
            customer_id=customer_id,
            content=email.body_plain,
            customer_name=email.from_name,
            customer_email=email.from_email,
        )

        if 'error' in result:
            logger.error(f"Error processing email: {result['error']}")
            return result

        # Send the reply email
        if result.get('response'):
            self._send_reply(platform, email, result['response'])

        return {
            'success': True,
            'conversation_id': result.get('conversation_id'),
            'response_type': result.get('response_type'),
            'needs_human_review': result.get('needs_human_review', False),
        }

    def _send_reply(
        self,
        platform: Platform,
        original_email: InboundEmail,
        response_content: str
    ):
        """Send reply email to customer."""

        # Get sender configuration from platform credentials
        credentials = platform.credentials or {}
        from_email = credentials.get('from_email', '')
        from_name = credentials.get('from_name', 'Support')

        if not from_email:
            logger.error("No from_email configured for platform")
            return

        sender = EmailSender()
        result = sender.send_reply(
            to=original_email.from_email,
            subject=original_email.subject,
            body=response_content,
            from_email=from_email,
            from_name=from_name,
            original_message_id=original_email.message_id,
        )

        if result.get('success'):
            logger.info(f"Reply sent to {original_email.from_email}")
        else:
            logger.error(f"Failed to send reply: {result.get('error')}")


@csrf_exempt
@require_POST
def email_webhook_simple(request, platform_id: str):
    """
    Simplified webhook endpoint that auto-detects provider.

    URL: /api/v1/webhooks/email/<platform_id>/
    """
    view = EmailWebhookView()

    # Try to detect provider from request
    provider = 'generic'

    # Check for SendGrid specific fields
    if 'envelope' in request.POST:
        provider = 'sendgrid'
    # Check for Mailgun specific fields
    elif 'body-plain' in request.POST and 'sender' in request.POST:
        provider = 'mailgun'
    # Check for Postmark (JSON body)
    elif request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            if 'FromFull' in data:
                provider = 'postmark'
        except json.JSONDecodeError:
            pass

    logger.info(f"Auto-detected email provider: {provider}")

    # Create a mock match object for the view
    request.resolver_match = type('obj', (object,), {
        'kwargs': {'provider': provider, 'platform_id': platform_id}
    })()

    return view.post(request, provider, platform_id)
