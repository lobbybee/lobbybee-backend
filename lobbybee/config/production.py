from .base import *

# Production-specific settings
DEBUG = False

# Database configuration for production
DATABASES['default'] = env.db()

# Security settings for production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_SECONDS = 31536000
SECURE_REDIRECT_EXEMPT = []
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# CORS settings for production
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

# Check if we're in Docker build phase (no S3 access needed)
DISABLE_S3 = env.bool('DISABLE_S3_DURING_BUILD', default=False)

if DISABLE_S3:
    # Use local storage during Docker build
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    STATIC_URL = '/static/'
    STATIC_ROOT = '/app/static'
    MEDIA_URL = '/media/'
    MEDIA_ROOT = '/app/media'
else:
    # AWS S3 settings for production runtime
    AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = env('AWS_DEFAULT_REGION')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'

    # S3 File Storage Settings
    AWS_DEFAULT_ACL = 'public-read'
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }
    AWS_S3_FILE_OVERWRITE = False
    AWS_QUERYSTRING_AUTH = False

    # Static and media files (Django 5.2+ format)
    STORAGES = {
        "default": {
            "BACKEND": "lobbybee.utils.storage_backends.MediaStorage",
        },
        "staticfiles": {
            "BACKEND": "lobbybee.utils.storage_backends.StaticStorage",
        },
    }

    # URLs for static and media files
    STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'

# Celery Configuration for production
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Email backend for production (using SMTP)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# Whatsapp
PHONE_NUMBER_ID = env('PHONE_NUMBER_ID_PROD')
