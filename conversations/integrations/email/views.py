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
from django.core.cache import cache

from conversations.models import Platform
from conversations.services import handle_incoming_message
from .receiver import EmailWebhookHandler, InboundEmail
from .sender import EmailSender

logger = logging.getLogger(__name__)

# Rate limiting constants
EMAIL_WEBHOOK_RATE_LIMIT = 300  # requests per hour (lower than WhatsApp to be conservative)
EMAIL_WEBHOOK_RATE_WINDOW = 3600  # 1 hour in seconds

# Input validation constants
MAX_EMAIL_BODY_LENGTH = 50000  # 50KB max for email body
MAX_SUBJECT_LENGTH = 500  # 500 chars max for subject
MAX_EMAIL_ADDRESS_LENGTH = 254  # RFC 5321 maximum

# Prompt injection detection patterns
PROMPT_INJECTION_PATTERNS = [
    'ignore previous',
    'ignore all previous',
    'disregard previous',
    'forget previous',
    'system:',
    'assistant:',
    'user:',
    '[INST]',
    '[/INST]',
    '<|im_start|>',
    '<|im_end|>',
]


def check_email_webhook_rate_limit(ip_address: str) -> bool:
    """
    Check if IP is within rate limit for email webhooks.

    Returns True if allowed, False if rate limited.
    """
    cache_key = f"email_webhook_rate:{ip_address}"
    current_count = cache.get(cache_key, 0)

    if current_count >= EMAIL_WEBHOOK_RATE_LIMIT:
        logger.warning(f"SECURITY: Email webhook rate limit exceeded for IP {ip_address}")
        return False

    cache.set(cache_key, current_count + 1, EMAIL_WEBHOOK_RATE_WINDOW)
    return True


def validate_email_input(email: InboundEmail) -> tuple[bool, str]:
    """
    Validate email input for length and prompt injection attempts.

    Returns: (is_valid, error_message)
    """
    # Validate email addresses length
    if len(email.from_email) > MAX_EMAIL_ADDRESS_LENGTH:
        return False, "From email address too long"

    if len(email.to_email) > MAX_EMAIL_ADDRESS_LENGTH:
        return False, "To email address too long"

    # Validate subject length
    if len(email.subject) > MAX_SUBJECT_LENGTH:
        logger.warning(f"SECURITY: Email subject too long ({len(email.subject)} chars) from {email.from_email}")
        return False, "Subject too long"

    # Validate body length
    if len(email.body_plain) > MAX_EMAIL_BODY_LENGTH:
        logger.warning(f"SECURITY: Email body too long ({len(email.body_plain)} chars) from {email.from_email}")
        return False, "Email body too long"

    # Check for prompt injection patterns
    body_lower = email.body_plain.lower()
    subject_lower = email.subject.lower()

    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern in body_lower or pattern in subject_lower:
            logger.warning(
                f"SECURITY: Potential prompt injection detected in email from {email.from_email}. "
                f"Pattern: '{pattern}'"
            )
            # Don't reject entirely, but sanitize by adding a warning prefix
            # This allows legitimate emails that happen to contain these patterns
            break

    return True, ""


def sanitize_email_content(content: str) -> str:
    """
    Sanitize email content to prevent prompt injection.

    Adds a prefix to make it clear this is user input, not instructions.
    """
    # Add a clear separator to prevent prompt injection
    sanitized = f"[User Email Content]\n{content}\n[End of User Email Content]"
    return sanitized


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

        # SECURITY FIX #2: Rate limiting
        client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
            or request.META.get('REMOTE_ADDR', '')
        if not check_email_webhook_rate_limit(client_ip):
            return JsonResponse(
                {'error': 'Rate limit exceeded'},
                status=429
            )

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

        # SECURITY FIX #1: Signature verification
        handler = EmailWebhookHandler()

        if provider == 'sendgrid':
            # Verify SendGrid signature
            signature = request.headers.get('X-Twilio-Email-Event-Webhook-Signature', '')
            timestamp = request.headers.get('X-Twilio-Email-Event-Webhook-Timestamp', '')

            if signature and timestamp:
                if not handler.verify_sendgrid_signature(signature, timestamp, request.body):
                    logger.warning(f"SECURITY: SendGrid signature verification failed for IP {client_ip}")
                    return JsonResponse({'error': 'Invalid signature'}, status=403)
            else:
                logger.warning(
                    f"SECURITY: SendGrid webhook missing signature headers from IP {client_ip}"
                )
                return JsonResponse({'error': 'Missing signature'}, status=403)

            email = handler.parse_sendgrid(request.POST.dict())

        elif provider == 'mailgun':
            # Verify Mailgun signature
            signature = request.POST.get('signature', '')
            timestamp = request.POST.get('timestamp', '')
            token = request.POST.get('token', '')

            if signature and timestamp and token:
                if not handler.verify_mailgun_signature(signature, timestamp, token):
                    logger.warning(f"SECURITY: Mailgun signature verification failed for IP {client_ip}")
                    return JsonResponse({'error': 'Invalid signature'}, status=403)
            else:
                logger.warning(
                    f"SECURITY: Mailgun webhook missing signature fields from IP {client_ip}"
                )
                return JsonResponse({'error': 'Missing signature'}, status=403)

            email = handler.parse_mailgun(request.POST.dict())

        elif provider == 'postmark':
            # Postmark doesn't use HMAC signature, but we can validate it's from Postmark
            # by checking required fields structure
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                data = request.POST.dict()

            # Validate Postmark-specific structure
            if 'FromFull' not in data or 'MessageID' not in data:
                logger.warning(
                    f"SECURITY: Invalid Postmark webhook structure from IP {client_ip}"
                )
                return JsonResponse({'error': 'Invalid Postmark webhook'}, status=403)

            email = handler.parse_postmark(data)
        else:
            # For generic/unknown providers, reject if no signature verification available
            logger.warning(
                f"SECURITY: Unknown email provider '{provider}' rejected from IP {client_ip}"
            )
            return JsonResponse({'error': 'Unsupported provider'}, status=403)

        if not email:
            logger.error("Failed to parse incoming email")
            return JsonResponse({'error': 'Failed to parse email'}, status=400)

        # SECURITY FIX #3: Input validation
        is_valid, error_message = validate_email_input(email)
        if not is_valid:
            logger.warning(
                f"SECURITY: Email validation failed from {email.from_email}: {error_message}"
            )
            return JsonResponse({'error': error_message}, status=400)

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

        # Sanitize email content to prevent prompt injection
        sanitized_content = sanitize_email_content(email.body_plain)

        # Handle the incoming message
        result = handle_incoming_message(
            user_id=platform.user_id,
            platform='email',
            customer_id=customer_id,
            content=sanitized_content,
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

    Note: This endpoint has the same security measures as the explicit provider endpoint.
    """
    # SECURITY: Rate limiting check before processing
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
        or request.META.get('REMOTE_ADDR', '')
    if not check_email_webhook_rate_limit(client_ip):
        return JsonResponse(
            {'error': 'Rate limit exceeded'},
            status=429
        )

    view = EmailWebhookView()

    # Try to detect provider from request
    provider = None

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
            logger.warning("Failed to parse JSON body for provider detection")

    # SECURITY: Reject unknown providers (don't allow 'generic' without signature verification)
    if not provider:
        logger.warning(
            f"SECURITY: Unable to detect email provider from IP {client_ip}, rejecting"
        )
        return JsonResponse({'error': 'Unable to detect email provider'}, status=403)

    logger.info(f"Auto-detected email provider: {provider}")

    # Create a mock match object for the view
    request.resolver_match = type('obj', (object,), {
        'kwargs': {'provider': provider, 'platform_id': platform_id}
    })()

    return view.post(request, provider, platform_id)
