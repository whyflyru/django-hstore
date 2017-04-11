from __future__ import print_function

import os
import sys

import django

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DEBUG = True

SECRET_KEY = '!5myuh^d23p9$$lo5k$39x&ji!vceayg+wwt472!bgs$0!i3k4'

DATABASES = {
    'default': {
        # possible backends are:
        #   * django.db.backends.postgresql_psycopg2
        #   * django.contrib.gis.db.backends.postgis
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'django_hstore',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': ''
    },
}

ALLOWED_HOSTS = []

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_hstore',
    'django_hstore_tests'
)

if django.VERSION[:2] >= (1, 7):
    INSTALLED_APPS = (
        'django.contrib.admin.apps.AdminConfig',
    ) + INSTALLED_APPS
else:
    INSTALLED_APPS = (
        'django.contrib.admin',
    ) + INSTALLED_APPS

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'urls'
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True
STATIC_URL = '/static/'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

# local settings must be imported before test runner otherwise they'll be ignored
try:
    from local_settings import *  # noqa
except ImportError:
    pass

if django.VERSION[:2] >= (1, 6):
    TEST_RUNNER = 'django.test.runner.DiscoverRunner'
else:
    try:
        import discover_runner  # noqa
        TEST_RUNNER = "discover_runner.DiscoverRunner"
    except ImportError:
        print("For run tests with django <= 1.5 you should install "
              "django-discover-runner.")
        sys.exit(-1)
