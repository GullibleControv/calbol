"""
WhatsApp Webhook Views

Handles:
- Webhook verification (GET request)
- Incoming message processing (POST request)
- Rate limiting to prevent webhook flooding
"""
import json
import logging
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from django.core.cache import cache

from conversations.models import Platform, Message
from .receiver import WhatsAppWebhookHandler
from .processor import WhatsAppProcessor

logger = logging.getLogger(__name__)

# Idempotency cache TTL (prevent duplicate processing within this window)
IDEMPOTENCY_CACHE_TTL = 3600  # 1 hour

# Rate limiting constants
WEBHOOK_RATE_LIMIT = 500  # requests per hour
WEBHOOK_RATE_WINDOW = 3600  # 1 hour in seconds


def check_webhook_rate_limit(ip_address: str) -> bool:
    """
    Check if IP is within rate limit for webhooks.

    Returns True if allowed, False if rate limited.
    """
    cache_key = f"webhook_rate:{ip_address}"
    current_count = cache.get(cache_key, 0)

    if current_count >= WEBHOOK_RATE_LIMIT:
        logger.warning(f"SECURITY: Webhook rate limit exceeded for IP {ip_address}")
        return False

    cache.set(cache_key, current_count + 1, WEBHOOK_RATE_WINDOW)
    return True


@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppWebhookView(View):
    """
    WhatsApp webhook endpoint.

    GET: Webhook verification (called by Meta when setting up webhook)
    POST: Incoming message handling
    """

    def get(self, request):
        """
        Handle webhook verification.

        Meta sends GET request with:
        - hub.mode: "subscribe"
        - hub.verify_token: Your verify token
        - hub.challenge: Random string to return

        Returns challenge if valid, 403 otherwise.
        """
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        handler = WhatsAppWebhookHandler()
        result = handler.verify_webhook(mode=mode, challenge=challenge, token=token)

        if result:
            logger.info("WhatsApp webhook verified successfully")
            return HttpResponse(result, content_type='text/plain')

        logger.warning("WhatsApp webhook verification failed")
        return HttpResponse("Verification failed", status=403)

    def post(self, request):
        """
        Handle incoming WhatsApp messages.

        Verifies signature, parses messages, and processes them.
        Rate limited to prevent webhook flooding.
        """
        # Rate limiting
        client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
            or request.META.get('REMOTE_ADDR', '')
        if not check_webhook_rate_limit(client_ip):
            return JsonResponse(
                {'error': 'Rate limit exceeded'},
                status=429
            )

        # Get signature from headers
        signature = request.headers.get('X-Hub-Signature-256', '')

        # Parse body
        try:
            body = request.body
            payload = json.loads(body)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in WhatsApp webhook")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        # Verify signature
        handler = WhatsAppWebhookHandler()
        if not handler.verify_signature(signature=signature, payload=body):
            logger.warning("WhatsApp webhook signature verification failed")
            return JsonResponse({'error': 'Invalid signature'}, status=403)

        # Parse messages
        messages = handler.parse_webhook(payload)

        if not messages:
            # Could be a status update or other non-message event
            return JsonResponse({'status': 'ok'})

        # Process each message
        results = []
        for message in messages:
            result = self._process_message(message)
            results.append(result)

        return JsonResponse({
            'status': 'ok',
            'processed': len(results),
            'results': results
        })

    def _process_message(self, message) -> dict:
        """
        Process a single message by finding the appropriate platform.

        Implements idempotency to prevent duplicate processing of webhooks.
        Uses indexed phone_number_id for O(1) platform lookup.

        Args:
            message: InboundWhatsAppMessage object

        Returns:
            dict with processing result
        """
        try:
            # IDEMPOTENCY CHECK: Prevent duplicate processing
            # WhatsApp may send the same webhook multiple times
            if message.message_id:
                # Check cache first (fast path)
                cache_key = f"wa_processed:{message.message_id}"
                if cache.get(cache_key):
                    logger.info(f"Skipping duplicate webhook (cache): {message.message_id}")
                    return {
                        'success': True,
                        'status': 'duplicate',
                        'from': message.from_number
                    }

                # Check database (authoritative)
                if Message.objects.filter(external_id=message.message_id).exists():
                    # Cache for future duplicate checks
                    cache.set(cache_key, True, IDEMPOTENCY_CACHE_TTL)
                    logger.info(f"Skipping duplicate webhook (db): {message.message_id}")
                    return {
                        'success': True,
                        'status': 'duplicate',
                        'from': message.from_number
                    }

            # OPTIMIZED PLATFORM LOOKUP: Use indexed phone_number_id field
            # O(1) lookup instead of loading all platforms and iterating
            platform = Platform.objects.filter(
                platform_type='whatsapp',
                phone_number_id=message.phone_number_id,
                is_active=True
            ).first()

            # Fallback: Check credentials field if phone_number_id not migrated yet
            if not platform:
                whatsapp_platforms = Platform.objects.filter(
                    platform_type='whatsapp',
                    is_active=True
                )
                for p in whatsapp_platforms:
                    if p.credentials.get('phone_number_id') == message.phone_number_id:
                        platform = p
                        # Auto-migrate: Update phone_number_id for future fast lookups
                        p.phone_number_id = message.phone_number_id
                        p.save(update_fields=['phone_number_id'])
                        logger.info(f"Auto-migrated phone_number_id for platform {p.id}")
                        break

            if not platform:
                logger.warning(
                    f"No WhatsApp platform found for phone_number_id: {message.phone_number_id}"
                )
                return {
                    'success': False,
                    'error': 'Platform not found',
                    'from': message.from_number
                }

            # Process the message (pass external_id for storage)
            processor = WhatsAppProcessor(platform)
            result = processor.process_inbound(message)
            result['from'] = message.from_number

            # Mark as processed in cache
            if message.message_id:
                cache.set(f"wa_processed:{message.message_id}", True, IDEMPOTENCY_CACHE_TTL)

            return result

        except Exception as e:
            logger.error(f"Error processing WhatsApp message: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Internal processing error',
                'from': message.from_number
            }


@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppStatusView(View):
    """
    WhatsApp integration status endpoint.

    Returns the current status of WhatsApp integration.
    """

    def get(self, request):
        """Return WhatsApp integration status."""
        platforms = Platform.objects.filter(
            platform_type='whatsapp',
            is_active=True
        ).count()

        return JsonResponse({
            'status': 'active' if platforms > 0 else 'not_configured',
            'active_platforms': platforms
        })
