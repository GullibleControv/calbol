from django.db import models
from django.conf import settings


class Platform(models.Model):
    """
    Platform Model

    Stores connected messaging platforms for each user.
    Each platform (Email, WhatsApp, Instagram) has its own credentials.

    Example:
        User connects their WhatsApp Business account
        - Platform type: "whatsapp"
        - Credentials: {"phone_id": "123", "access_token": "..."}
        - is_active: True
    """

    PLATFORM_CHOICES = [
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
        ('instagram', 'Instagram'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='platforms'
    )

    platform_type = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        help_text="Type of messaging platform"
    )

    # Enable/disable this platform connection
    is_active = models.BooleanField(
        default=True,
        help_text="Whether auto-replies are enabled for this platform"
    )

    # Platform-specific credentials (stored as encrypted JSON)
    # WARNING: In production, encrypt these credentials!
    credentials = models.JSONField(
        default=dict,
        blank=True,
        help_text="API tokens and credentials for this platform"
    )

    # Platform-specific settings
    settings_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Platform-specific settings (reply delay, etc.)"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Connected Platform"
        verbose_name_plural = "Connected Platforms"
        # Each user can only connect one account per platform type
        unique_together = ['user', 'platform_type']

    def __str__(self):
        status = "🟢" if self.is_active else "🔴"
        return f"{status} {self.get_platform_type_display()} ({self.user.email})"


class Conversation(models.Model):
    """
    Conversation Model

    Groups messages between a business and a customer.
    One conversation per customer per platform.

    Example:
        Customer "John" messages on WhatsApp
        -> Creates Conversation(customer_name="John", platform="whatsapp")
        -> All messages with John are linked to this conversation
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations'
    )

    # Which platform this conversation is on
    platform = models.CharField(
        max_length=20,
        help_text="Platform where this conversation is happening"
    )

    # Customer identifier (platform-specific ID)
    customer_id = models.CharField(
        max_length=255,
        help_text="Platform-specific customer identifier"
    )

    # Customer info (if available)
    customer_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Customer's name (if available)"
    )

    customer_email = models.EmailField(
        blank=True,
        help_text="Customer's email (if available)"
    )

    customer_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Customer's phone number (if available)"
    )

    # Conversation status
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('resolved', 'Resolved'),
        ('waiting', 'Waiting for Customer'),
        ('escalated', 'Escalated to Human'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        help_text="Current status of the conversation"
    )

    # Flag for human review
    needs_human_review = models.BooleanField(
        default=False,
        help_text="True if AI couldn't handle and needs human attention"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"
        ordering = ['-updated_at']  # Most recent activity first
        # One conversation per customer per platform per user
        unique_together = ['user', 'platform', 'customer_id']

    def __str__(self):
        name = self.customer_name or self.customer_id[:20]
        return f"{name} via {self.platform}"

    def get_message_count(self):
        """Return total number of messages in this conversation."""
        return self.messages.count()

    def get_last_message(self):
        """Return the most recent message."""
        return self.messages.order_by('-created_at').first()


class Message(models.Model):
    """
    Message Model

    Individual messages within a conversation.
    Tracks whether it's from customer (inbound) or business (outbound).
    Also tracks how the response was generated.

    Example flow:
        1. Customer sends: "What are your prices?"
           -> Message(direction="inbound", content="What are your prices?")

        2. System finds predefined reply match
           -> Message(direction="outbound", response_type="predefined", content="...")

        3. Or AI generates response
           -> Message(direction="outbound", response_type="ai", ai_confidence=0.85)
    """

    DIRECTION_CHOICES = [
        ('inbound', 'Inbound'),    # Customer -> Business
        ('outbound', 'Outbound'),  # Business -> Customer
    ]

    RESPONSE_TYPE_CHOICES = [
        ('predefined', 'Predefined Reply'),  # Matched a keyword
        ('ai', 'AI Generated'),              # AI generated from knowledge base
        ('manual', 'Manual'),                # Human typed the response
        ('fallback', 'Fallback'),            # Default "I'll get back to you" message
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )

    # Message direction
    direction = models.CharField(
        max_length=10,
        choices=DIRECTION_CHOICES,
        help_text="Whether message is from customer or business"
    )

    # Message content
    content = models.TextField(
        help_text="The actual message text"
    )

    # For outbound messages: how was the response generated?
    response_type = models.CharField(
        max_length=20,
        choices=RESPONSE_TYPE_CHOICES,
        null=True,
        blank=True,
        help_text="How the response was generated (for outbound only)"
    )

    # AI confidence score (0.0 to 1.0)
    ai_confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="AI's confidence in its response (0.0 to 1.0)"
    )

    # Link to which predefined reply was used (if any)
    predefined_reply = models.ForeignKey(
        'replies.PredefinedReply',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages_sent',
        help_text="Which predefined reply was used (if applicable)"
    )

    # Processing metadata
    processing_time_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="How long it took to generate the response (milliseconds)"
    )

    # Error tracking
    error_message = models.TextField(
        blank=True,
        help_text="Error message if sending failed"
    )

    is_delivered = models.BooleanField(
        default=True,
        help_text="Whether the message was successfully delivered"
    )

    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ['created_at']  # Chronological order

    def __str__(self):
        direction_arrow = "←" if self.direction == "inbound" else "→"
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"{direction_arrow} {preview}"

    def is_from_customer(self):
        """Check if this message is from the customer."""
        return self.direction == 'inbound'

    def is_ai_response(self):
        """Check if this was an AI-generated response."""
        return self.response_type == 'ai'

    def get_response_type_display_with_confidence(self):
        """Return response type with confidence if AI."""
        if self.response_type == 'ai' and self.ai_confidence:
            confidence_pct = int(self.ai_confidence * 100)
            return f"AI ({confidence_pct}% confident)"
        return self.get_response_type_display()
