"""
Django settings for CalBol project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-this-in-production')

# Encryption key for sensitive fields (uses SECRET_KEY by default)
# IMPORTANT: Changing this will make existing encrypted data unreadable
SALT_KEY = os.getenv('SALT_KEY', SECRET_KEY)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_htmx',
    'drf_spectacular',

    # Local apps
    'accounts',
    'replies',
    'knowledge',
    'conversations',
    'dashboard',
    'analytics',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',  # i18n - must be after SessionMiddleware
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'config.middleware.SecurityHeadersMiddleware',  # Custom security headers (CSP, etc.)
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# Use SQLite for local development, PostgreSQL (Supabase) for production
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(default=DATABASE_URL)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Authentication backends - allow login with email
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    # API Documentation schema
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # Rate Limiting (Security)
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',      # Anonymous requests
        'user': '1000/hour',     # Authenticated requests
        'auth': '10/minute',     # Login attempts (prevent brute force)
        'ai': '50/hour',         # AI generation (prevent quota abuse)
        'webhook': '500/hour',   # Webhook endpoints
        'upload': '20/hour',     # File uploads
    },
}

# drf-spectacular API Documentation Settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'CalBol API',
    'DESCRIPTION': '''
## CalBol Auto-Reply SaaS API

CalBol helps businesses automatically respond to customer inquiries across multiple messaging platforms.

### Features
- **Predefined Replies**: Keyword-based auto-responses
- **AI-Powered Responses**: RAG-based intelligent replies using your knowledge base
- **Multi-Platform**: Email, WhatsApp, Instagram support
- **Knowledge Base**: Upload documents to power AI responses

### Authentication
All API endpoints require JWT authentication.

1. Obtain a token: `POST /api/v1/auth/token/`
2. Include in requests: `Authorization: Bearer <access_token>`
3. Refresh tokens: `POST /api/v1/auth/token/refresh/`

### Rate Limits
- Free plan: 50 replies/month
- Starter plan: 1,000 replies/month
- Pro plan: Unlimited
    ''',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'CONTACT': {
        'name': 'CalBol Support',
        'email': 'support@calbol.com',
    },
    'LICENSE': {
        'name': 'Proprietary',
    },
    'TAGS': [
        {'name': 'auth', 'description': 'Authentication endpoints'},
        {'name': 'replies', 'description': 'Predefined reply management'},
        {'name': 'documents', 'description': 'Knowledge base document management'},
        {'name': 'conversations', 'description': 'Conversation management'},
        {'name': 'platforms', 'description': 'Platform connections'},
        {'name': 'messages', 'description': 'Message history'},
        {'name': 'ai', 'description': 'AI testing endpoints'},
        {'name': 'email', 'description': 'Email integration'},
    ],
    'COMPONENT_SPLIT_REQUEST': True,
    'SWAGGER_UI_SETTINGS': {
        'persistAuthorization': True,
        'filter': True,
    },
}

# JWT Settings
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}


# CORS settings
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
CORS_ALLOW_CREDENTIALS = True


# Internationalization
from django.utils.translation import gettext_lazy as _

LANGUAGE_CODE = 'en'
TIME_ZONE = 'Asia/Tokyo'  # Japan timezone
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Supported languages
LANGUAGES = [
    ('en', _('English')),
    ('ja', _('Japanese')),
]

# Path to locale files
LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# Language cookie settings
LANGUAGE_COOKIE_NAME = 'calbol_language'
LANGUAGE_COOKIE_AGE = 365 * 24 * 60 * 60  # 1 year


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise for serving static files
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Media files (User uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Login URLs
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# Session settings - unique cookie name to avoid conflicts with other Django projects
SESSION_COOKIE_NAME = 'calbol_sessionid'
CSRF_COOKIE_NAME = 'calbol_csrftoken'


# Celery Configuration
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'


# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')


# Email Configuration (Resend)
RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')


# WhatsApp Cloud API Configuration
WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', '')
WHATSAPP_APP_SECRET = os.getenv('WHATSAPP_APP_SECRET', '')
WHATSAPP_ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN', '')
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')


# =============================================================================
# Sentry Error Monitoring
# =============================================================================
SENTRY_DSN = os.getenv('SENTRY_DSN', '')

if SENTRY_DSN and not DEBUG:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(
                transaction_style="url",
                middleware_spans=True,
            ),
            CeleryIntegration(),
            RedisIntegration(),
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR,
            ),
        ],
        # Performance monitoring
        traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
        # Profile 10% of transactions for performance insights
        profiles_sample_rate=float(os.getenv('SENTRY_PROFILES_SAMPLE_RATE', '0.1')),
        # Environment tag
        environment=os.getenv('SENTRY_ENVIRONMENT', 'production'),
        # Release version
        release=os.getenv('SENTRY_RELEASE', 'calbol@1.0.0'),
        # Don't send PII
        send_default_pii=False,
        # Filter out health check transactions
        before_send_transaction=lambda event, hint: None if event.get('transaction') in ['/health/', '/ready/'] else event,
    )


# =============================================================================
# Structured Logging Configuration
# =============================================================================
import logging

# Request ID middleware for correlation
MIDDLEWARE.insert(0, 'config.middleware.RequestIDMiddleware')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'json': {
            '()': 'config.logging.JsonFormatter',
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'request_id': {
            '()': 'config.logging.RequestIDFilter',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'json' if not DEBUG else 'verbose',
            'filters': ['request_id'],
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'calbol.log',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
            'formatter': 'json',
            'filters': ['request_id'],
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'errors.log',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
            'formatter': 'json',
            'filters': ['request_id'],
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false'],
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'error_file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console', 'error_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        # Application loggers
        'accounts': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'conversations': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'knowledge': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'replies': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# =============================================================================
# Request Size Limits (Security - prevent DoS)
# =============================================================================
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100  # Limit form fields


# =============================================================================
# Production Security Settings
# =============================================================================
if not DEBUG:
    # Validate critical production settings
    from django.core.exceptions import ImproperlyConfigured

    # Ensure secure SECRET_KEY
    if SECRET_KEY.startswith('django-insecure'):
        raise ImproperlyConfigured(
            "SECURITY ERROR: SECRET_KEY must be changed for production. "
            "Generate a new key with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
        )

    if len(SECRET_KEY) < 50:
        raise ImproperlyConfigured(
            "SECURITY ERROR: SECRET_KEY is too short. Use at least 50 characters."
        )

    # HTTPS/SSL settings
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    # Cookie security
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Content security
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

    # Validate webhook secrets are configured
    if not WHATSAPP_APP_SECRET:
        logging.warning(
            "SECURITY WARNING: WHATSAPP_APP_SECRET not configured. "
            "WhatsApp webhooks will reject all requests."
        )
