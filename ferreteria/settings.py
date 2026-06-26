"""

Django settings for the hardware store internal web app.

Optimized for small deployment: SQLite by default, single process.

"""

import os

from pathlib import Path



from dotenv import load_dotenv



load_dotenv()



BASE_DIR = Path(__file__).resolve().parent.parent



SECRET_KEY = os.environ.get(

    "DJANGO_SECRET_KEY",

    "dev-insecure-change-me-in-production",

)



DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"



ALLOWED_HOSTS = [

    h.strip()

    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

    if h.strip()

]



INSTALLED_APPS = [

    "core",

    "warehouse",

    "sales",

    "django.contrib.admin",

    "django.contrib.auth",

    "django.contrib.contenttypes",

    "django.contrib.sessions",

    "django.contrib.messages",

    "django.contrib.staticfiles",

    "rest_framework",

]



REST_FRAMEWORK = {

    "DEFAULT_AUTHENTICATION_CLASSES": [

        "rest_framework.authentication.SessionAuthentication",

    ],

    "DEFAULT_PERMISSION_CLASSES": [

        "rest_framework.permissions.IsAuthenticated",

    ],

    "DEFAULT_RENDERER_CLASSES": [

        "rest_framework.renderers.JSONRenderer",

    ],

}



MIDDLEWARE = [

    "django.middleware.security.SecurityMiddleware",

    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",

    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    "core.middleware.DefaultStoreMiddleware",

]



ROOT_URLCONF = "ferreteria.urls"



TEMPLATES = [

    {

        "BACKEND": "django.template.backends.django.DjangoTemplates",

        "DIRS": [],

        "APP_DIRS": True,

        "OPTIONS": {

            "context_processors": [

                "django.template.context_processors.debug",

                "django.template.context_processors.request",

                "django.contrib.auth.context_processors.auth",

                "django.contrib.messages.context_processors.messages",

                "core.context_processors.default_store",

            ],

        },

    },

]



WSGI_APPLICATION = "ferreteria.wsgi.application"



_sqlite_path = BASE_DIR / "data" / "db.sqlite3"

_sqlite_path.parent.mkdir(parents=True, exist_ok=True)



DATABASES = {

    "default": {

        "ENGINE": "django.db.backends.sqlite3",

        "NAME": _sqlite_path,

    }

}



AUTH_PASSWORD_VALIDATORS = [

    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},

    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},

    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},

    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},

]



LANGUAGE_CODE = "es-es"

TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "America/Mexico_City")

USE_I18N = True

USE_TZ = True



STATIC_URL = "static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [

    d
    for d in (
        BASE_DIR / "core" / "static",
        BASE_DIR / "warehouse" / "static",
        BASE_DIR / "sales" / "static",
    )
    if d.exists()

]

STORAGES = {

    "default": {

        "BACKEND": "django.core.files.storage.FileSystemStorage",

    },

    "staticfiles": {

        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",

    },

}



DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"



LOGIN_URL = "login"

LOGIN_REDIRECT_URL = "home"

LOGOUT_REDIRECT_URL = "login"



EOD_EXPORT_DIR = Path(os.environ.get("EOD_EXPORT_DIR", str(BASE_DIR / "exports")))



DEFAULT_STORE_CODE = os.environ.get("DEFAULT_STORE_CODE", "principal")



# Production hardening (active when DJANGO_DEBUG=0).

# This deployment serves plain HTTP over the local store network (no HTTPS),

# so cookie-secure / SSL-redirect flags are intentionally left disabled.

CSRF_TRUSTED_ORIGINS = [

    origin

    for host in ALLOWED_HOSTS

    for origin in (f"http://{host}", f"http://{host}:80")

    if host not in ("127.0.0.1", "localhost")

]

if not DEBUG:

    SESSION_COOKIE_HTTPONLY = True

    SECURE_CONTENT_TYPE_NOSNIFF = True

    X_FRAME_OPTIONS = "DENY"

    USE_X_FORWARDED_HOST = False


