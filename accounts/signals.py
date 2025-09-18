# accounts/signals.py
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomerProfile

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_customer_profile(sender, instance, created, **kwargs):
    """
    Create a profile when a new User is created.
    Uses get_or_create to be idempotent (safe on retries).
    """
    if created:
        CustomerProfile.objects.get_or_create(user=instance, defaults={"user_type": getattr(instance, "role", None)})