"""
API URL Configuration for CalBol.

All API endpoints are prefixed with /api/v1/
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# Import API viewsets
from replies.api import PredefinedReplyViewSet
from knowledge.api import DocumentViewSet
from conversations.api import (
    PlatformViewSet,
    ConversationViewSet,
    MessageViewSet,
    AITestViewSet,
    EmailIntegrationViewSet
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'replies', PredefinedReplyViewSet, basename='reply')
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'platforms', PlatformViewSet, basename='platform')
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'messages', MessageViewSet, basename='message')
router.register(r'ai', AITestViewSet, basename='ai')
router.register(r'email', EmailIntegrationViewSet, basename='email')

urlpatterns = [
    # JWT Authentication
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Webhooks (no authentication required - verified by signature)
    path('webhooks/email/', include('conversations.integrations.email.urls')),

    # API endpoints (registered via router)
    path('', include(router.urls)),
]
