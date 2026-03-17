"""
Email Sender Service

Sends emails using Resend API.
"""
import logging
import requests
from django.conf import settings
from typing import Optional, List

logger = logging.getLogger(__name__)


class EmailSender:
    """
    Send emails via Resend API.

    Usage:
        sender = EmailSender()
        sender.send(
            to="customer@example.com",
            subject="Re: Your inquiry",
            body="Thank you for contacting us...",
            from_email="support@yourbusiness.com"
        )
    """

    API_URL = "https://api.resend.com/emails"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.RESEND_API_KEY
        if not self.api_key:
            logger.warning("Resend API key not configured")

    def send(
        self,
        to: str | List[str],
        subject: str,
        body: str,
        from_email: str,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        html: Optional[str] = None,
    ) -> dict:
        """
        Send an email.

        Args:
            to: Recipient email address(es)
            subject: Email subject
            body: Plain text body
            from_email: Sender email address
            from_name: Sender display name
            reply_to: Reply-to address
            html: HTML body (optional, uses plain text if not provided)

        Returns:
            dict with 'success' and 'id' or 'error'
        """
        if not self.api_key:
            logger.error("Cannot send email: Resend API key not configured")
            return {'success': False, 'error': 'API key not configured'}

        # Format the from field
        if from_name:
            from_field = f"{from_name} <{from_email}>"
        else:
            from_field = from_email

        # Ensure 'to' is a list
        if isinstance(to, str):
            to = [to]

        # Build request payload
        payload = {
            "from": from_field,
            "to": to,
            "subject": subject,
            "text": body,
        }

        if html:
            payload["html"] = html

        if reply_to:
            payload["reply_to"] = reply_to

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                self.API_URL,
                json=payload,
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                logger.info(f"Email sent successfully to {to}, ID: {data.get('id')}")
                return {'success': True, 'id': data.get('id')}
            else:
                error_msg = response.json().get('message', response.text)
                logger.error(f"Failed to send email: {error_msg}")
                return {'success': False, 'error': error_msg}

        except requests.exceptions.Timeout:
            logger.error("Email send timeout")
            return {'success': False, 'error': 'Request timeout'}
        except requests.exceptions.RequestException as e:
            logger.error(f"Email send error: {e}")
            return {'success': False, 'error': str(e)}

    def send_reply(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: str,
        from_name: str = "Support",
        original_message_id: Optional[str] = None,
    ) -> dict:
        """
        Send a reply email (adds Re: prefix if needed).

        Args:
            to: Recipient email
            subject: Original subject (Re: will be added if missing)
            body: Reply body
            from_email: Sender email
            from_name: Sender name
            original_message_id: Original email Message-ID for threading
        """
        # Add Re: prefix if not present
        if not subject.lower().startswith('re:'):
            subject = f"Re: {subject}"

        return self.send(
            to=to,
            subject=subject,
            body=body,
            from_email=from_email,
            from_name=from_name,
            reply_to=from_email,
        )


def send_email(
    to: str,
    subject: str,
    body: str,
    from_email: str,
    from_name: Optional[str] = None
) -> dict:
    """
    Convenience function to send an email.

    Usage:
        from conversations.integrations.email import send_email

        result = send_email(
            to="customer@example.com",
            subject="Hello",
            body="Thank you for your inquiry.",
            from_email="support@business.com",
            from_name="Support Team"
        )
    """
    sender = EmailSender()
    return sender.send(
        to=to,
        subject=subject,
        body=body,
        from_email=from_email,
        from_name=from_name
    )
