import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
ENVIRONMENT = os.environ.get("DJANGO_ENV", "production")
if ENVIRONMENT not in {"development", "production", "test"}:
    raise ImproperlyConfigured("Unknown DJANGO_ENV")
DEBUG = ENVIRONMENT == "development"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must contain at least 50 characters")
if SECRET_KEY.startswith("replace"):
    # The placeholder of .env.example is long enough to pass the length check.
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is still the example value")
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
DATA_MODE = os.environ.get("DATA_MODE", "production")
if DATA_MODE not in {"production", "training"}:
    raise ImproperlyConfigured("DATA_MODE must be production or training")
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "rest_framework",
    "drf_spectacular",
    "catalog",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "rescue.middleware.ContentSecurityPolicy",
    # Serves /static/ and, in the production image, the built frontend (FRONTEND_DIST).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # The administration follows the browser's language (English or French).
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "rescue.middleware.APIRequestLimit",
]
# Local machine only: sign every visitor in as this account, so no sign-in screen is needed while
# the project runs on a laptop. Refused outside development, where the sign-in stays mandatory.
LOCAL_AUTO_LOGIN = os.environ.get("LOCAL_AUTO_LOGIN", "")
if LOCAL_AUTO_LOGIN:
    if ENVIRONMENT != "development":
        raise ImproperlyConfigured("LOCAL_AUTO_LOGIN is allowed only with DJANGO_ENV=development")
    MIDDLEWARE.insert(
        MIDDLEWARE.index("django.contrib.auth.middleware.AuthenticationMiddleware") + 1,
        "rescue.middleware.LocalAutoLogin",
    )
ROOT_URLCONF = "rescue.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "rescue.wsgi.application"
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
if not DB_PASSWORD:
    raise ImproperlyConfigured("DB_PASSWORD is required")
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.environ.get("POSTGRES_DB", "rescue"),
        "USER": os.environ.get("DB_USER", "rescue"),
        "PASSWORD": DB_PASSWORD,
        "HOST": os.environ.get("DB_HOST", "db"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        # A connection dropped by the database is replaced instead of failing the next request.
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"options": "-c statement_timeout=10000"},
    }
}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "fr-fr"
LANGUAGES = [("en", "English"), ("fr", "Français")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
# Production image: the built frontend (frontend/dist) is served by the same process as the API.
# Its files answer at the root; every other path that is not the API, the admin or /static/ gets
# index.html, so the application's own routes load (rescue/urls.py).
FRONTEND_DIST = os.environ.get("FRONTEND_DIST", "")
if FRONTEND_DIST:
    WHITENOISE_ROOT = FRONTEND_DIST
    WHITENOISE_INDEX_FILE = True
    # Vite names every built asset after its content: cache them for good.
    WHITENOISE_IMMUTABLE_FILE_TEST = lambda path, url: url.startswith("/assets/")  # noqa: E731
    WHITENOISE_MIMETYPES = {".geojson": "application/geo+json"}

    def WHITENOISE_ADD_HEADERS_FUNCTION(headers, path, url):  # noqa: N802
        # The page names the hashed assets of its release: never serve a stale one.
        if url in ("/", "/index.html"):
            headers["Cache-Control"] = "no-cache"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATA_UPLOAD_MAX_MEMORY_SIZE = 65536
FILE_UPLOAD_MAX_MEMORY_SIZE = 65536
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = ENVIRONMENT == "production"
SECURE_HSTS_SECONDS = 31536000 if ENVIRONMENT == "production" else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = ENVIRONMENT == "production"
SECURE_HSTS_PRELOAD = ENVIRONMENT == "production"
X_FRAME_OPTIONS = "DENY"
# The proxy's health probe may speak plain HTTP inside the server.
SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
# Behind a proxy that terminates TLS, Django must trust its header or SECURE_SSL_REDIRECT loops.
# Set only when that proxy always overwrites the header (Django deployment checklist).
if os.environ.get("DJANGO_BEHIND_TLS_PROXY") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Number of proxies in front of Django. 0 ignores X-Forwarded-For, so a client cannot change the
# address its sign-in attempts are counted under; set it to the real number of proxies.
NUM_PROXIES = int(os.environ.get("DJANGO_NUM_PROXIES", "0"))
# Shared by every worker, so the sign-in limit holds across processes and restarts.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

CSRF_TRUSTED_ORIGINS = [
    value
    for value in os.environ.get(
        "CSRF_TRUSTED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173" if DEBUG else ""
    ).split(",")
    if value
]

# JSON file naming the source key and the CSV export URL of each tab (ADR 0012); local, not committed.
SHEETS_SYNC_CONFIG = os.environ.get("SHEETS_SYNC_CONFIG", "")

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAdminUser"],
    "URL_FORMAT_OVERRIDE": None,
    "EXCEPTION_HANDLER": "catalog.api.exception_handler",
    "NUM_PROXIES": NUM_PROXIES,
    # Sign-in attempts per client address, counted in the shared database cache.
    "DEFAULT_THROTTLE_RATES": {
        "sign_in": os.environ.get("SIGN_IN_RATE", "10/min"),
        "imports": os.environ.get("IMPORT_RATE", "30/min"),
        "invitations": os.environ.get("INVITATION_RATE", "20/min"),
    },
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Mediterranean Rescue public API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    # Tags come from the first segment after the version, for public and private paths alike.
    "SCHEMA_PATH_PREFIX": r"/api/(?:private/)?v1",
    # Stable enum names: KindEnum is used by the frontend; the private API adds its own.
    "ENUM_NAME_OVERRIDES": {
        "KindEnum": "catalog.models.EventKind",
        "ReviewProposalEnum": "catalog.private_api.PROPOSAL_KINDS",
        "ReviewStatusEnum": "catalog.private_api.STATUSES",
        "SheetEnum": "catalog.models.SHEETS",
        "PortLabelStatusEnum": "catalog.private_ports.LABEL_STATUSES",
        "PortInterpretationEnum": "catalog.private_ports.INTERPRETATIONS",
        "IssueSeverityEnum": "catalog.private_imports.SEVERITIES",
        "BlockingReasonEnum": "catalog.private_imports.BLOCKING_REASONS",
        "PublicationActionEnum": "catalog.private_publication.PUBLICATION_ACTIONS",
        "PublicationStatusEnum": "catalog.private_publication.EVENT_STATUSES",
    },
}
