"""
WhatsApp Message Sender

Sends messages via WhatsApp Cloud API.
Supports:
- Text messages
- Template messages
- Media messages (image, document, video, audio)
- Interactive messages (buttons, lists)
- Mark as read
"""
import logging
import requests
import json
from django.conf import settings
from typing import Optional, List

logger = logging.getLogger(__name__)


class WhatsAppSender:
    """
    Send messages via WhatsApp Cloud API.

    Usage:
        sender = WhatsAppSender(phone_number_id="123456")
        result = sender.send_text(to="15559876543", message="Hello!")
    """

    API_BASE = "https://graph.facebook.com/v18.0"

    def __init__(
        self,
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None
    ):
        """
        Initialize sender.

        Args:
            phone_number_id: WhatsApp phone number ID from Meta dashboard
            access_token: Access token for API authentication
        """
        self.phone_number_id = phone_number_id or getattr(
            settings, 'WHATSAPP_PHONE_NUMBER_ID', ''
        )
        self.access_token = access_token or getattr(
            settings, 'WHATSAPP_ACCESS_TOKEN', ''
        )

    def _get_api_url(self) -> str:
        """Get the API endpoint URL."""
        return f"{self.API_BASE}/{self.phone_number_id}/messages"

    def _get_headers(self) -> dict:
        """Get request headers."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def _validate_config(self) -> Optional[dict]:
        """Validate configuration. Returns error dict if invalid."""
        if not self.access_token:
            return {'success': False, 'error': 'Access token not configured'}
        if not self.phone_number_id:
            return {'success': False, 'error': 'Phone number ID not configured'}
        return None

    def _send_request(self, payload: dict) -> dict:
        """
        Send API request.

        Args:
            payload: Request payload

        Returns:
            dict with success status and message_id or error
        """
        validation_error = self._validate_config()
        if validation_error:
            return validation_error

        try:
            response = requests.post(
                self._get_api_url(),
                headers=self._get_headers(),
                json=payload,
                timeout=30
            )

            data = response.json()

            if response.status_code == 200:
                message_id = data.get('messages', [{}])[0].get('id', '')
                logger.info(f"WhatsApp message sent: {message_id}")
                return {'success': True, 'message_id': message_id}
            else:
                error = data.get('error', {})
                error_msg = error.get('message', str(data))
                logger.error(f"WhatsApp API error: {error_msg}")
                return {'success': False, 'error': error_msg}

        except requests.exceptions.Timeout:
            logger.error("WhatsApp API timeout")
            return {'success': False, 'error': 'Request timeout'}
        except requests.exceptions.RequestException as e:
            logger.error(f"WhatsApp API error: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"WhatsApp send error: {e}")
            return {'success': False, 'error': str(e)}

    def send_text(
        self,
        to: str,
        message: str,
        preview_url: bool = False,
        reply_to_message_id: Optional[str] = None
    ) -> dict:
        """
        Send a text message.

        Args:
            to: Recipient phone number (with country code, no +)
            message: Text message content
            preview_url: Whether to show URL previews
            reply_to_message_id: Message ID to reply to (for threading)

        Returns:
            dict with success status
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": message
            }
        }

        if reply_to_message_id:
            payload["context"] = {
                "message_id": reply_to_message_id
            }

        return self._send_request(payload)

    def send_template(
        self,
        to: str,
        template_name: str,
        language: str = "en",
        components: Optional[List[dict]] = None
    ) -> dict:
        """
        Send a template message.

        Args:
            to: Recipient phone number
            template_name: Name of the approved template
            language: Template language code
            components: Template components (header, body, buttons)

        Returns:
            dict with success status
        """
        template = {
            "name": template_name,
            "language": {
                "code": language
            }
        }

        if components:
            template["components"] = components

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": template
        }

        return self._send_request(payload)

    def send_image(
        self,
        to: str,
        image_url: Optional[str] = None,
        image_id: Optional[str] = None,
        caption: Optional[str] = None
    ) -> dict:
        """
        Send an image message.

        Args:
            to: Recipient phone number
            image_url: URL of the image (public URL)
            image_id: Media ID of uploaded image
            caption: Image caption

        Returns:
            dict with success status
        """
        image_data = {}
        if image_url:
            image_data["link"] = image_url
        elif image_id:
            image_data["id"] = image_id

        if caption:
            image_data["caption"] = caption

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": image_data
        }

        return self._send_request(payload)

    def send_document(
        self,
        to: str,
        document_url: Optional[str] = None,
        document_id: Optional[str] = None,
        filename: Optional[str] = None,
        caption: Optional[str] = None
    ) -> dict:
        """
        Send a document message.

        Args:
            to: Recipient phone number
            document_url: URL of the document
            document_id: Media ID of uploaded document
            filename: Document filename
            caption: Document caption

        Returns:
            dict with success status
        """
        doc_data = {}
        if document_url:
            doc_data["link"] = document_url
        elif document_id:
            doc_data["id"] = document_id

        if filename:
            doc_data["filename"] = filename
        if caption:
            doc_data["caption"] = caption

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "document",
            "document": doc_data
        }

        return self._send_request(payload)

    def send_buttons(
        self,
        to: str,
        body_text: str,
        buttons: List[dict],
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None
    ) -> dict:
        """
        Send an interactive button message.

        Args:
            to: Recipient phone number
            body_text: Main message body
            buttons: List of buttons, each with 'id' and 'title'
            header_text: Optional header text
            footer_text: Optional footer text

        Returns:
            dict with success status
        """
        interactive = {
            "type": "button",
            "body": {"text": body_text},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": btn["id"],
                            "title": btn["title"]
                        }
                    }
                    for btn in buttons[:3]  # Max 3 buttons
                ]
            }
        }

        if header_text:
            interactive["header"] = {"type": "text", "text": header_text}
        if footer_text:
            interactive["footer"] = {"text": footer_text}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive
        }

        return self._send_request(payload)

    def send_list(
        self,
        to: str,
        body_text: str,
        button_text: str,
        sections: List[dict],
        header_text: Optional[str] = None,
        footer_text: Optional[str] = None
    ) -> dict:
        """
        Send an interactive list message.

        Args:
            to: Recipient phone number
            body_text: Main message body
            button_text: Text for the list button
            sections: List sections with rows
            header_text: Optional header text
            footer_text: Optional footer text

        Returns:
            dict with success status
        """
        interactive = {
            "type": "list",
            "body": {"text": body_text},
            "action": {
                "button": button_text,
                "sections": sections
            }
        }

        if header_text:
            interactive["header"] = {"type": "text", "text": header_text}
        if footer_text:
            interactive["footer"] = {"text": footer_text}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive
        }

        return self._send_request(payload)

    def mark_as_read(self, message_id: str) -> dict:
        """
        Mark a message as read.

        Args:
            message_id: ID of the message to mark as read

        Returns:
            dict with success status
        """
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }

        return self._send_request(payload)

    def send_reply(
        self,
        to: str,
        message: str,
        original_message_id: str
    ) -> dict:
        """
        Send a reply to a specific message.

        Args:
            to: Recipient phone number
            message: Reply text
            original_message_id: Message ID to reply to

        Returns:
            dict with success status
        """
        return self.send_text(
            to=to,
            message=message,
            reply_to_message_id=original_message_id
        )


def send_whatsapp_message(
    to: str,
    message: str,
    phone_number_id: Optional[str] = None
) -> dict:
    """
    Convenience function to send a WhatsApp message.

    Usage:
        from conversations.integrations.whatsapp import send_whatsapp_message

        result = send_whatsapp_message(
            to="15559876543",
            message="Hello!"
        )
    """
    sender = WhatsAppSender(phone_number_id=phone_number_id)
    return sender.send_text(to=to, message=message)
