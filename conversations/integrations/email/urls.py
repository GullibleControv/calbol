"""
Email Webhook URLs
"""
from django.urls import path
from .views import EmailWebhookView, email_webhook_simple

app_name = 'email_webhooks'

urlpatterns = [
    # Provider-specific webhook
    # POST /api/v1/webhooks/email/<provider>/<platform_id>/
    path(
        '<str:provider>/<str:platform_id>/',
        EmailWebhookView.as_view(),
        name='provider_webhook'
    ),

    # Auto-detect provider webhook
    # POST /api/v1/webhooks/email/<platform_id>/
    path(
        '<str:platform_id>/',
        email_webhook_simple,
        name='simple_webhook'
    ),
]
