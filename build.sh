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
# Provide secure values in Render's Environment settings.
python - <<'PY'
import os
from django.contrib.auth import get_user_model
import django
django.setup()
User = get_user_model()
username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "changeme")
if not User.objects.filter(username=username).exists():
    print("Creating superuser:", username)
    User.objects.create_superuser(username=username, email=email, password=password)
else:
    print("Superuser already exists:", username)
PY
