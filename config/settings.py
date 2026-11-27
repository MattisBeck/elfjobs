import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Alle Einstellungen kommen aus Umgebungsvariablen (siehe .env).
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "jobs",
    "studies",
    "accounts",
    "timetable",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["POSTGRES_DB"],
        "USER": os.environ["POSTGRES_USER"],
        "PASSWORD": os.environ["POSTGRES_PASSWORD"],
        "HOST": os.environ["POSTGRES_HOST"],
        "PORT": os.environ["POSTGRES_PORT"],
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "de-de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

LOGIN_URL = "login"

# Mails (Bestätigung der Uni-Mail, #31). Im Dev-Setup landen sie in der Konsole:
# docker compose logs backend. Ein echter Mailserver kommt erst für Produktion.
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@elfjobs.local")
# Closed Access: Registrieren nur mit Mail dieser Hochschulen (Domain oder Subdomain,
# z. B. student.hpi.uni-potsdam.de). Zum Start nur das HPI, weitere Unis hier ergänzen.
UNI_EMAIL_DOMAINS = [
    "hpi.de",
    "hpi.uni-potsdam.de",
]
LOGIN_REDIRECT_URL = "job_list"
LOGOUT_REDIRECT_URL = "job_list"

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Anreisedauer mit ÖPNV: VBB-API von transport.rest, ohne Key.
TRAVEL_API_URL = os.environ.get("TRAVEL_API_URL", "https://v6.vbb.transport.rest")
TRAVEL_API_TIMEOUT = float(os.environ.get("TRAVEL_API_TIMEOUT", "5"))  # Sekunden
