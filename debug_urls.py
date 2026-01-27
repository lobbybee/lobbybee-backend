
import os
import django
import sys
from django.urls import URLPattern, URLResolver

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lobbybee.settings')
django.setup()

def inspect(urlpatterns, prefix=''):
    print(f"Inspecting {len(urlpatterns)} patterns at prefix '{prefix}'")
    for pattern in urlpatterns:
        if isinstance(pattern, URLResolver):
            print(f"  [RESOLVER] {pattern.pattern} -> {pattern.url_patterns[:1]}...")
            inspect(pattern.url_patterns, prefix + str(pattern.pattern))
        elif isinstance(pattern, URLPattern):
            print(f"  [PATTERN] {prefix}{pattern.pattern} -> {pattern.callback}")
            if hasattr(pattern.callback, 'cls'):
                 print(f"      View Class: {pattern.callback.cls.__name__}")
            else:
                 print(f"      No cls attribute")

from django.urls import get_resolver
resolver = get_resolver()
inspect(resolver.url_patterns)
