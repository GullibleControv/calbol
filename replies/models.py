from django.db import models
from django.conf import settings


class PredefinedReply(models.Model):
    """
    Predefined Reply Model

    Stores pre-written responses that business owners create for common questions.
    When a customer message matches the keywords, this reply is sent automatically.

    Example:
        Name: "Pricing Question"
        Keywords: ["price", "cost", "how much", "rate"]
        Response: "Our haircut prices start at ₹150. Visit us Mon-Sat 10AM-7PM."
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,  # Delete replies if user is deleted
        related_name='predefined_replies'  # Access via user.predefined_replies.all()
    )

    # Descriptive name for the reply (for dashboard display)
    name = models.CharField(
        max_length=100,
        help_text="A descriptive name like 'Pricing Question' or 'Location Info'"
    )

    # Keywords that trigger this reply (stored as JSON array)
    keywords = models.JSONField(
        default=list,
        help_text="List of trigger words: ['price', 'cost', 'how much']"
    )

    # The actual response text to send
    response = models.TextField(
        help_text="The message that will be sent to customers"
    )

    # Toggle to enable/disable without deleting
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive replies won't be used for matching"
    )

    # Track how many times this reply was used
    use_count = models.IntegerField(
        default=0,
        help_text="Number of times this reply was sent"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Predefined Reply"
        verbose_name_plural = "Predefined Replies"
        ordering = ['-created_at']  # Newest first

    def __str__(self):
        return f"{self.name} ({self.user.email})"

    def increment_use_count(self):
        """Call this when the reply is used to respond to a customer."""
        self.use_count += 1
        self.save(update_fields=['use_count'])

    def matches_message(self, message_text):
        """
        Check if the incoming message contains any of our keywords.

        Args:
            message_text: The customer's message

        Returns:
            bool: True if any keyword is found in the message
        """
        if not self.is_active:
            return False

        message_lower = message_text.lower()
        for keyword in self.keywords:
            if keyword.lower() in message_lower:
                return True
        return False
