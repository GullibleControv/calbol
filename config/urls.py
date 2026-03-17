"""
URL configuration for CalBol project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.conf.urls.i18n import i18n_patterns

# Non-internationalized URLs (API, etc.)
urlpatterns = [
    # REST API (v1) - not translated
    path('api/v1/', include('config.api_urls')),

    # Language switching
    path('i18n/', include('django.conf.urls.i18n')),
]

# Internationalized URLs (user-facing pages)
urlpatterns += i18n_patterns(
    # Admin
    path('admin/', admin.site.urls),

    # Authentication (login, register, logout)
    path('auth/', include('accounts.urls')),

    # Dashboard (main app)
    path('dashboard/', include('dashboard.urls')),

    # Replies CRUD
    path('replies/', include('replies.urls')),

    # Knowledge Base
    path('knowledge/', include('knowledge.urls')),

    # Redirect root to dashboard
    path('', RedirectView.as_view(url='/dashboard/', permanent=False), name='home'),

    # Don't add language prefix for default language (optional)
    prefix_default_language=True,
)

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
