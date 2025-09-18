# accounts/apps.py
from django.apps import AppConfig

class AccountsConfig(AppConfig):
    name = "accounts"          # must match your package import path
    # label = "accounts"      # leave default unless you know what you're doing

    def ready(self):
        # import signals so they get registered
        from . import signals  # noqa: F401