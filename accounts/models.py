from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model for CalBol.
    Extends Django's AbstractUser to add business-specific fields.
    """

    PLAN_CHOICES = [
        ('free', 'Free'),
        ('starter', 'Starter'),
        ('pro', 'Pro'),
    ]

    email = models.EmailField(unique=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free')
    company_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    # Monthly usage tracking
    monthly_replies = models.IntegerField(default=0)
    monthly_ai_replies = models.IntegerField(default=0)

    # Make email the primary login field
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.email

    def get_plan_limit(self):
        """Return monthly reply limit based on plan."""
        limits = {
            'free': 50,
            'starter': 1000,
            'pro': float('inf'),  # Unlimited
        }
        return limits.get(self.plan, 50)

    def can_send_reply(self):
        """Check if user has remaining replies in their plan."""
        return self.monthly_replies < self.get_plan_limit()
