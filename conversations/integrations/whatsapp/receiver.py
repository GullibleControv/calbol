"""
WhatsApp Webhook Receiver

Handles incoming WhatsApp messages from the WhatsApp Cloud API.
Supports:
- Webhook verification (GET request)
- Message parsing (POST request)
- Signature verification
"""
import logging
import hashlib
import hmac
from typing import Optional, List
from dataclasses import dataclass, field
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class InboundWhatsAppMessage:
    """Parsed inbound WhatsApp message data."""
    from_number: str
    from_name: str
    to_number: str
    message_id: str
    message_type: str
    timestamp: str
    phone_number_id: str

    # Text message
    text: Optional[str] = None

    # Media message fields
    media_id: Optional[str] = None
    mime_type: Optional[str] = None
    caption: Optional[str] = None
    filename: Optional[str] = None

    # Location message fields
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    location_address: Optional[str] = None

    # Context (reply/reaction)
    context_message_id: Optional[str] = None

    def get_display_content(self) -> str:
        """
        Get human-readable content for display/processing.

        Returns:
            str: Display content based on message type
        """
        if self.message_type == "text":
            return self.text or ""

        elif self.message_type in ("image", "video", "audio", "sticker"):
            type_label = self.message_type.capitalize()
            if self.caption:
                return f"[{type_label}] {self.caption}"
            return f"[{type_label}]"

        elif self.message_type == "document":
            if self.caption:
                return f"[Document: {self.filename or 'file'}] {self.caption}"
            return f"[Document: {self.filename or 'file'}]"

        elif self.message_type == "location":
            if self.location_name:
                return f"[Location] {self.location_name}"
            return f"[Location] {self.latitude}, {self.longitude}"

        elif self.message_type == "contacts":
            return "[Contact shared]"

        else:
            return f"[{self.message_type}]"


class WhatsAppWebhookHandler:
    """
    Handle WhatsApp Cloud API webhooks.

    Usage:
        handler = WhatsAppWebhookHandler(verify_token="my_token")

        # Verify webhook (GET request)
        challenge = handler.verify_webhook(mode, challenge, token)

        # Parse messages (POST request)
        messages = handler.parse_webhook(payload)
    """

    def __init__(
        self,
        verify_token: Optional[str] = None,
        app_secret: Optional[str] = None
    ):
        """
        Initialize handler.

        Args:
            verify_token: Token for webhook verification (from Meta dashboard)
            app_secret: App secret for signature verification
        """
        self.verify_token = verify_token or getattr(
            settings, 'WHATSAPP_VERIFY_TOKEN', ''
        )
        self.app_secret = app_secret or getattr(
            settings, 'WHATSAPP_APP_SECRET', ''
        )

    def verify_webhook(
        self,
        mode: Optional[str],
        challenge: Optional[str],
        token: Optional[str]
    ) -> Optional[str]:
        """
        Verify webhook subscription (handle GET request).

        WhatsApp sends GET request with:
        - hub.mode = "subscribe"
        - hub.challenge = random string (return this if valid)
        - hub.verify_token = your verify token

        Args:
            mode: hub.mode parameter
            challenge: hub.challenge parameter
            token: hub.verify_token parameter

        Returns:
            challenge string if valid, None otherwise
        """
        if mode != "subscribe":
            logger.warning(f"Invalid webhook mode: {mode}")
            return None

        if not token or not challenge:
            logger.warning("Missing token or challenge")
            return None

        if token != self.verify_token:
            logger.warning("Webhook verification failed: token mismatch")
            return None

        logger.info("WhatsApp webhook verified successfully")
        return challenge

    def verify_signature(
        self,
        signature: str,
        payload: bytes
    ) -> bool:
        """
        Verify webhook signature.

        WhatsApp signs webhooks with X-Hub-Signature-256 header:
        sha256=<signature>

        Args:
            signature: X-Hub-Signature-256 header value
            payload: Raw request body bytes

        Returns:
            True if valid, False otherwise
        """
        if not self.app_secret:
            logger.error(
                "SECURITY: WhatsApp app secret not configured - rejecting webhook. "
                "Set WHATSAPP_APP_SECRET in environment variables."
            )
            return False  # Secure default: reject when not configured

        if not signature.startswith("sha256="):
            logger.warning("Invalid signature format")
            return False

        expected_signature = signature[7:]  # Remove "sha256=" prefix

        computed_signature = hmac.new(
            self.app_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        if hmac.compare_digest(computed_signature, expected_signature):
            return True

        logger.warning("WhatsApp signature verification failed")
        return False

    def parse_webhook(self, payload: dict) -> List[InboundWhatsAppMessage]:
        """
        Parse WhatsApp webhook payload.

        Args:
            payload: Parsed JSON webhook payload

        Returns:
            List of InboundWhatsAppMessage objects
        """
        messages = []

        # Verify it's a WhatsApp webhook
        if payload.get("object") != "whatsapp_business_account":
            return messages

        entries = payload.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})

                # Skip if not a message webhook
                if "messages" not in value:
                    continue

                # Get metadata
                metadata = value.get("metadata", {})
                phone_number_id = metadata.get("phone_number_id", "")
                display_phone = metadata.get("display_phone_number", "")

                # Get contact info
                contacts = value.get("contacts", [{}])
                contact = contacts[0] if contacts else {}
                profile = contact.get("profile", {})
                from_name = profile.get("name", "")

                # Parse each message
                for msg_data in value.get("messages", []):
                    msg = self._parse_message(
                        msg_data=msg_data,
                        from_name=from_name,
                        to_number=display_phone,
                        phone_number_id=phone_number_id
                    )
                    if msg:
                        messages.append(msg)

        return messages

    def _parse_message(
        self,
        msg_data: dict,
        from_name: str,
        to_number: str,
        phone_number_id: str
    ) -> Optional[InboundWhatsAppMessage]:
        """Parse a single message from webhook data."""
        try:
            msg_type = msg_data.get("type", "unknown")

            # Base message data
            message = InboundWhatsAppMessage(
                from_number=msg_data.get("from", ""),
                from_name=from_name,
                to_number=to_number,
                message_id=msg_data.get("id", ""),
                message_type=msg_type,
                timestamp=msg_data.get("timestamp", ""),
                phone_number_id=phone_number_id,
            )

            # Parse type-specific data
            if msg_type == "text":
                text_data = msg_data.get("text", {})
                message.text = text_data.get("body", "")

            elif msg_type in ("image", "video", "audio", "sticker"):
                media_data = msg_data.get(msg_type, {})
                message.media_id = media_data.get("id")
                message.mime_type = media_data.get("mime_type")
                message.caption = media_data.get("caption")

            elif msg_type == "document":
                doc_data = msg_data.get("document", {})
                message.media_id = doc_data.get("id")
                message.mime_type = doc_data.get("mime_type")
                message.caption = doc_data.get("caption")
                message.filename = doc_data.get("filename")

            elif msg_type == "location":
                loc_data = msg_data.get("location", {})
                message.latitude = loc_data.get("latitude")
                message.longitude = loc_data.get("longitude")
                message.location_name = loc_data.get("name")
                message.location_address = loc_data.get("address")

            # Check for context (reply)
            context = msg_data.get("context", {})
            if context:
                message.context_message_id = context.get("id")

            logger.info(
                f"Parsed WhatsApp {msg_type} message from {message.from_number}"
            )
            return message

        except Exception as e:
            logger.error(f"Error parsing WhatsApp message: {e}")
            return None
