"""
WSGI config for wholesale_catalog project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
# --- ADD THESE TWO LINES ---
from dotenv import load_dotenv
load_dotenv()
# --- END OF ADDITION ---

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wholesale_catalog.settings')

application = get_wsgi_application()
