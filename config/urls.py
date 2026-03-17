"""
URL configuration for CalBol project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
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

    # REST API (v1)
    path('api/v1/', include('config.api_urls')),

    # Redirect root to dashboard (or login if not authenticated)
    path('', RedirectView.as_view(url='/dashboard/', permanent=False), name='home'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
