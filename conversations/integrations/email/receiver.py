"""
Email Webhook Receiver

Handles incoming emails from various email service providers:
- SendGrid Inbound Parse
- Mailgun Routes
- Postmark Inbound
"""
import logging
import hashlib
import hmac
import json
from typing import Optional, Tuple
from dataclasses import dataclass
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class InboundEmail:
    """Parsed inbound email data."""
    from_email: str
    from_name: str
    to_email: str
    subject: str
    body_plain: str
    body_html: Optional[str] = None
    message_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    attachments: list = None

    def __post_init__(self):
        if self.attachments is None:
            self.attachments = []


class EmailWebhookHandler:
    """
    Parse incoming email webhooks from various providers.

    Usage:
        handler = EmailWebhookHandler()
        email = handler.parse_sendgrid(request.POST)
        # or
        email = handler.parse_mailgun(request.POST)
    """

    def parse_sendgrid(self, data: dict) -> Optional[InboundEmail]:
        """
        Parse SendGrid Inbound Parse webhook.

        SendGrid sends POST data with these fields:
        - from: "Name <email@example.com>" or "email@example.com"
        - to: recipient email
        - subject: email subject
        - text: plain text body
        - html: HTML body
        - envelope: JSON with actual to/from
        """
        try:
            # Parse 'from' field
            from_field = data.get('from', '')
            from_name, from_email = self._parse_email_field(from_field)

            # Parse 'to' field
            to_field = data.get('to', '')
            _, to_email = self._parse_email_field(to_field)

            # Get envelope for more accurate addresses
            envelope = data.get('envelope')
            if envelope:
                if isinstance(envelope, str):
                    envelope = json.loads(envelope)
                from_email = envelope.get('from', from_email)
                to_list = envelope.get('to', [])
                if to_list:
                    to_email = to_list[0]

            email = InboundEmail(
                from_email=from_email,
                from_name=from_name,
                to_email=to_email,
                subject=data.get('subject', '(No Subject)'),
                body_plain=data.get('text', ''),
                body_html=data.get('html'),
                message_id=data.get('message-id'),
                in_reply_to=data.get('in-reply-to'),
            )

            logger.info(f"Parsed SendGrid email from {from_email} to {to_email}")
            return email

        except Exception as e:
            logger.error(f"Error parsing SendGrid webhook: {e}")
            return None

    def parse_mailgun(self, data: dict) -> Optional[InboundEmail]:
        """
        Parse Mailgun inbound webhook.

        Mailgun sends POST data with these fields:
        - sender: sender email
        - from: "Name <email>" format
        - recipient: recipient email
        - subject: email subject
        - body-plain: plain text body
        - body-html: HTML body
        """
        try:
            from_field = data.get('from', data.get('sender', ''))
            from_name, from_email = self._parse_email_field(from_field)

            # Use sender field as fallback for email
            if not from_email:
                from_email = data.get('sender', '')

            email = InboundEmail(
                from_email=from_email,
                from_name=from_name,
                to_email=data.get('recipient', ''),
                subject=data.get('subject', '(No Subject)'),
                body_plain=data.get('body-plain', ''),
                body_html=data.get('body-html'),
                message_id=data.get('Message-Id'),
                in_reply_to=data.get('In-Reply-To'),
            )

            logger.info(f"Parsed Mailgun email from {from_email}")
            return email

        except Exception as e:
            logger.error(f"Error parsing Mailgun webhook: {e}")
            return None

    def parse_postmark(self, data: dict) -> Optional[InboundEmail]:
        """
        Parse Postmark inbound webhook (JSON format).

        Postmark sends JSON with:
        - FromFull: {Email, Name}
        - ToFull: [{Email, Name}]
        - Subject
        - TextBody
        - HtmlBody
        """
        try:
            from_data = data.get('FromFull', {})
            to_data = data.get('ToFull', [{}])[0]

            email = InboundEmail(
                from_email=from_data.get('Email', ''),
                from_name=from_data.get('Name', ''),
                to_email=to_data.get('Email', ''),
                subject=data.get('Subject', '(No Subject)'),
                body_plain=data.get('TextBody', ''),
                body_html=data.get('HtmlBody'),
                message_id=data.get('MessageID'),
                in_reply_to=data.get('Headers', {}).get('In-Reply-To'),
            )

            logger.info(f"Parsed Postmark email from {email.from_email}")
            return email

        except Exception as e:
            logger.error(f"Error parsing Postmark webhook: {e}")
            return None

    def parse_generic(self, data: dict) -> Optional[InboundEmail]:
        """
        Try to parse email from generic/unknown format.
        Attempts to find common field names.
        """
        try:
            # Try various field names for 'from'
            from_field = (
                data.get('from') or
                data.get('From') or
                data.get('sender') or
                data.get('from_email') or
                ''
            )
            from_name, from_email = self._parse_email_field(from_field)

            # Try various field names for 'to'
            to_field = (
                data.get('to') or
                data.get('To') or
                data.get('recipient') or
                data.get('to_email') or
                ''
            )
            _, to_email = self._parse_email_field(to_field)

            # Try various field names for body
            body = (
                data.get('text') or
                data.get('body') or
                data.get('body-plain') or
                data.get('TextBody') or
                data.get('content') or
                ''
            )

            email = InboundEmail(
                from_email=from_email,
                from_name=from_name,
                to_email=to_email,
                subject=data.get('subject', data.get('Subject', '(No Subject)')),
                body_plain=body,
                body_html=data.get('html', data.get('body-html', data.get('HtmlBody'))),
            )

            logger.info(f"Parsed generic email from {from_email}")
            return email

        except Exception as e:
            logger.error(f"Error parsing generic webhook: {e}")
            return None

    def _parse_email_field(self, field: str) -> Tuple[str, str]:
        """
        Parse email field that might be in format:
        - "Name <email@example.com>"
        - "email@example.com"

        Returns: (name, email)
        """
        if not field:
            return ('', '')

        field = field.strip()

        # Check for "Name <email>" format
        if '<' in field and '>' in field:
            parts = field.split('<')
            name = parts[0].strip().strip('"\'')
            email = parts[1].rstrip('>').strip()
            return (name, email)

        # Just an email address
        return ('', field)

    def verify_sendgrid_signature(
        self,
        signature: str,
        timestamp: str,
        body: bytes
    ) -> bool:
        """Verify SendGrid webhook signature."""
        webhook_key = getattr(settings, 'SENDGRID_WEBHOOK_KEY', '')
        if not webhook_key:
            logger.warning("SendGrid webhook key not configured")
            return True  # Skip verification if not configured

        payload = f"{timestamp}{body.decode('utf-8')}"
        expected = hmac.new(
            webhook_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected)

    def verify_mailgun_signature(
        self,
        signature: str,
        timestamp: str,
        token: str
    ) -> bool:
        """Verify Mailgun webhook signature."""
        api_key = getattr(settings, 'MAILGUN_API_KEY', '')
        if not api_key:
            logger.warning("Mailgun API key not configured")
            return True  # Skip verification if not configured

        payload = f"{timestamp}{token}"
        expected = hmac.new(
            api_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected)
