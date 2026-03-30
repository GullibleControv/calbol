"""
WhatsApp URL Configuration

Webhook endpoints for WhatsApp Cloud API integration.
"""
from django.urls import path
from .views import WhatsAppWebhookView, WhatsAppStatusView

app_name = 'whatsapp'

urlpatterns = [
    # Main webhook endpoint (handles both GET verification and POST messages)
    path('webhook/', WhatsAppWebhookView.as_view(), name='webhook'),

    # Status endpoint
    path('status/', WhatsAppStatusView.as_view(), name='status'),
]
