"""
Tests for WhatsApp webhook views.

Tests:
- Webhook verification (GET)
- Message processing (POST)
- Error handling
"""
import json
import pytest
import hmac
import hashlib
import uuid
from unittest.mock import patch, MagicMock
from django.test import Client, override_settings
from django.core.cache import cache
from django.urls import reverse

from conversations.models import Platform


@pytest.mark.django_db
class TestWhatsAppWebhookVerification:
    """Tests for webhook verification (GET request)."""

    @pytest.fixture
    def client(self):
        return Client()

    @override_settings(WHATSAPP_VERIFY_TOKEN='test_verify_token')
    def test_webhook_verification_success(self, client):
        """Test successful webhook verification."""
        response = client.get(
            '/api/v1/webhooks/whatsapp/webhook/',
            {
                'hub.mode': 'subscribe',
                'hub.verify_token': 'test_verify_token',
                'hub.challenge': 'challenge_123'
            }
        )

        assert response.status_code == 200
        assert response.content == b'challenge_123'

    @override_settings(WHATSAPP_VERIFY_TOKEN='test_verify_token')
    def test_webhook_verification_wrong_token(self, client):
        """Test webhook verification with wrong token."""
        response = client.get(
            '/api/v1/webhooks/whatsapp/webhook/',
            {
                'hub.mode': 'subscribe',
                'hub.verify_token': 'wrong_token',
                'hub.challenge': 'challenge_123'
            }
        )

        assert response.status_code == 403

    def test_webhook_verification_missing_params(self, client):
        """Test webhook verification with missing parameters."""
        response = client.get('/api/v1/webhooks/whatsapp/webhook/')

        assert response.status_code == 403


@pytest.mark.django_db
class TestWhatsAppWebhookPost:
    """Tests for webhook POST (incoming messages)."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear cache before each test to prevent idempotency false positives."""
        cache.clear()
        yield
        cache.clear()

    @pytest.fixture
    def client(self):
        return Client()

    @pytest.fixture
    def user(self):
        from accounts.models import User
        return User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    @pytest.fixture
    def whatsapp_platform(self, user):
        return Platform.objects.create(
            user=user,
            platform_type='whatsapp',
            is_active=True,
            credentials={
                'phone_number_id': '123456789',
                'access_token': 'test_token'
            }
        )

    @pytest.fixture
    def message_payload(self):
        """Generate unique message payload for each test (prevents idempotency cache collision)."""
        unique_id = f"wamid.{uuid.uuid4().hex[:12]}"
        return {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15551234567",
                            "phone_number_id": "123456789"
                        },
                        "contacts": [{
                            "profile": {"name": "Test User"},
                            "wa_id": "15559876543"
                        }],
                        "messages": [{
                            "from": "15559876543",
                            "id": unique_id,
                            "timestamp": "1699900000",
                            "text": {"body": "Hello, I need help!"},
                            "type": "text"
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }

    def _sign_payload(self, payload: bytes, secret: str) -> str:
        """Generate webhook signature."""
        signature = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"

    @override_settings(WHATSAPP_APP_SECRET='test_secret')
    @patch('conversations.integrations.whatsapp.views.WhatsAppProcessor')
    def test_webhook_post_processes_message(
        self, mock_processor_class, client, whatsapp_platform, message_payload
    ):
        """Test webhook POST processes incoming message."""
        mock_processor = MagicMock()
        mock_processor.process_inbound.return_value = {
            'success': True,
            'conversation_id': 1,
            'message_id': 1
        }
        mock_processor_class.return_value = mock_processor

        payload = json.dumps(message_payload).encode()
        signature = self._sign_payload(payload, 'test_secret')

        response = client.post(
            '/api/v1/webhooks/whatsapp/webhook/',
            payload,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=signature
        )

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        assert data['processed'] == 1

    def test_webhook_post_invalid_json(self, client):
        """Test webhook POST with invalid JSON."""
        response = client.post(
            '/api/v1/webhooks/whatsapp/webhook/',
            'not valid json',
            content_type='application/json'
        )

        assert response.status_code == 400
        assert 'Invalid JSON' in response.json()['error']

    @override_settings(WHATSAPP_APP_SECRET='test_secret')
    def test_webhook_post_invalid_signature(self, client, message_payload):
        """Test webhook POST with invalid signature."""
        payload = json.dumps(message_payload).encode()

        response = client.post(
            '/api/v1/webhooks/whatsapp/webhook/',
            payload,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256='sha256=invalid_signature'
        )

        assert response.status_code == 403

    @override_settings(WHATSAPP_APP_SECRET='')
    def test_webhook_post_no_secret_configured(
        self, client, whatsapp_platform, message_payload
    ):
        """Test webhook POST rejected when no secret is configured (secure default)."""
        payload = json.dumps(message_payload).encode()

        response = client.post(
            '/api/v1/webhooks/whatsapp/webhook/',
            payload,
            content_type='application/json'
        )

        # Secure default: reject when no secret configured
        assert response.status_code == 403

    @override_settings(WHATSAPP_APP_SECRET='test_secret')
    def test_webhook_post_status_update(self, client):
        """Test webhook POST with status update (not a message)."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15551234567",
                            "phone_number_id": "123456789"
                        },
                        "statuses": [{
                            "id": "wamid.test123",
                            "status": "delivered"
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }

        payload_bytes = json.dumps(payload).encode()
        signature = self._sign_payload(payload_bytes, 'test_secret')

        response = client.post(
            '/api/v1/webhooks/whatsapp/webhook/',
            payload_bytes,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=signature
        )

        assert response.status_code == 200
        assert response.json()['status'] == 'ok'

    @override_settings(WHATSAPP_APP_SECRET='test_secret')
    def test_webhook_post_no_platform_found(self, client, message_payload):
        """Test webhook POST when no platform is configured."""
        # No platform created
        payload = json.dumps(message_payload).encode()
        signature = self._sign_payload(payload, 'test_secret')

        response = client.post(
            '/api/v1/webhooks/whatsapp/webhook/',
            payload,
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=signature
        )

        assert response.status_code == 200
        data = response.json()
        assert data['processed'] == 1
        assert data['results'][0]['success'] is False
        assert 'Platform not found' in data['results'][0]['error']


@pytest.mark.django_db
class TestWhatsAppStatusView:
    """Tests for WhatsApp status endpoint."""

    @pytest.fixture
    def client(self):
        return Client()

    @pytest.fixture
    def user(self):
        from accounts.models import User
        return User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_status_not_configured(self, client):
        """Test status when no platforms configured."""
        response = client.get('/api/v1/webhooks/whatsapp/status/')

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'not_configured'
        assert data['active_platforms'] == 0

    def test_status_active(self, client, user):
        """Test status with active platform."""
        Platform.objects.create(
            user=user,
            platform_type='whatsapp',
            is_active=True,
            credentials={'phone_number_id': '123'}
        )

        response = client.get('/api/v1/webhooks/whatsapp/status/')

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'active'
        assert data['active_platforms'] == 1
