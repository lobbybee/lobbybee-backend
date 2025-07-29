"""
This file acts as a settings switcher.

It reads the DJANGO_ENV environment variable to determine which settings file to use.
By default, it uses the development settings.
"""

from .config.base import *
from .config.development import *


# You can switch between environments by setting the DJANGO_ENV variable.
# For example, to use production settings:
# export DJANGO_ENV=production
# python manage.py runserver

import os

env = os.environ.get('DJANGO_ENV', 'development')

if env == 'production':
    from .config.production import *