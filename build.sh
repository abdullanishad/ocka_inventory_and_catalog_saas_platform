#!/usr/bin/env bash
set -euo pipefail

# install dependencies
pip install -r requirements.txt

# collect static files
python manage.py collectstatic --no-input

# run migrations (non-interactive)
python manage.py migrate --no-input

# Create a superuser automatically if none exists.
# Reads env vars DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, DJANGO_SUPERUSER_PASSWORD.
# This runs inside manage.py shell so DJANGO_SETTINGS_MODULE is set.
python manage.py shell <<'PY'
import os
from django.contrib.auth import get_user_model

User = get_user_model()
username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "changeme")

if not User.objects.filter(username=username).exists():
    print("Creating superuser:", username)
    User.objects.create_superuser(username, email, password)
else:
    print("Superuser already exists:", username)
PY
