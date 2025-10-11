# accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class Organization(models.Model):
    WHOLESALER = "wholesaler"
    RETAILER = "retailer"
    ORG_TYPES = [(WHOLESALER, "Wholesaler"), (RETAILER, "Retailer")]

    name = models.CharField(max_length=200)
    org_type = models.CharField(max_length=20, choices=ORG_TYPES)

    def __str__(self):
        return f"{self.name} ({self.org_type})"


class User(AbstractUser):
    # primary role (used for UX & default permissions)
    role = models.CharField(
        max_length=20,
        choices=[("wholesaler", "Wholesaler"), ("retailer", "Retailer")],
        default="retailer",
    )
    # each user belongs to exactly one org for now (simple)
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="users", null=True, blank=True
    )

from django.conf import settings
from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_save

# If using Django >= 3.1, use models.JSONField; else from django.contrib.postgres.fields import JSONField

# --- UPDATED CustomerProfile Model ---
class CustomerProfile(models.Model):
    USER_TYPE_CHOICES = [("retailer", "Retailer"), ("wholesaler", "Wholesaler")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")

    # Business Identity
    business_logo = models.ImageField(upload_to="logos/", blank=True, null=True)
    about_us = models.TextField(blank=True, null=True)
    year_established = models.PositiveIntegerField(blank=True, null=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, blank=True, null=True)

    # Contact Info
    phone = models.CharField(max_length=30, blank=True, null=True)
    whatsapp_number = models.CharField(max_length=30, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    instagram_link = models.URLField(blank=True, null=True)

    # Address
    street_address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=120, blank=True, null=True)
    state = models.CharField(max_length=120, blank=True, null=True)
    pincode = models.CharField(max_length=20, blank=True, null=True)

    # Verification and Tax
    gstin = models.CharField(max_length=30, blank=True, null=True)
    is_verified = models.BooleanField(default=False)

     # === ADD THIS NEW SECTION FOR BANK DETAILS ===
    bank_account_holder_name = models.CharField(max_length=100, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    bank_account_number = models.CharField(max_length=30, blank=True, null=True)
    bank_ifsc_code = models.CharField(max_length=20, blank=True, null=True)
    
    # Delivery options
    supports_doorstep = models.BooleanField(default=False)
    supports_hub = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Customer Profile"
        verbose_name_plural = "Customer Profiles"

    def __str__(self):
        return f"{self.user.username} profile"

    @property
    def is_wholesaler(self):
        # prefer explicit profile value if set else fall back to user.role
        return (self.user_type == "wholesaler") or (getattr(self.user, "role", None) == "wholesaler")

    @property
    def is_retailer(self):
        return (self.user_type == "retailer") or (getattr(self.user, "role", None) == "retailer")

    def get_min_order_qty(self):
        return self.min_order_qty or (self.extra or {}).get("min_order_qty")