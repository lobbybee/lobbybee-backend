import os

# Always import base first
from .config.base import *

# Check environment BEFORE importing any environment-specific settings
env = os.environ.get('DJANGO_ENV', 'development')

if env == 'production':
    from .config.production import *
    print("Production settings imported")
else:
    from .config.development import *
    print("Development settings imported")
