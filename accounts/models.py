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

class CustomerProfile(models.Model):
    RETAILER = "retailer"
    WHOLESALER = "wholesaler"
    USER_TYPE_CHOICES = [(RETAILER, "Retailer"), (WHOLESALER, "Wholesaler")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")

    # optional — copy of role for quick access/search (keeps profile self-contained)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, blank=True, null=True)

    # contact / business info
    phone = models.CharField(max_length=30, blank=True, null=True)
    street_address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=120, blank=True, null=True)
    state = models.CharField(max_length=120, blank=True, null=True)
    pincode = models.CharField(max_length=20, blank=True, null=True)

    # B2B / wholesale fields (optional)
    min_order_qty = models.PositiveIntegerField(blank=True, null=True)
    wholesale_discount_pct = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    # verification and documents
    gstin = models.CharField(max_length=30, blank=True, null=True)
    gst_doc = models.FileField(upload_to="docs/gst/", blank=True, null=True)   # optional file fields
    trade_license = models.FileField(upload_to="docs/licenses/", blank=True, null=True)
    is_verified = models.BooleanField(default=False)

    # flexible field for strange/rare attributes
    extra = models.JSONField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Customer Profile"
        verbose_name_plural = "Customer Profiles"
        indexes = [
            models.Index(fields=["user_type"]),
            models.Index(fields=["is_verified"]),
        ]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} profile"

    @property
    def is_wholesaler(self):
        # prefer explicit profile value if set else fall back to user.role
        return (self.user_type == self.WHOLESALER) or (getattr(self.user, "role", None) == self.WHOLESALER)

    @property
    def is_retailer(self):
        return (self.user_type == self.RETAILER) or (getattr(self.user, "role", None) == self.RETAILER)

    def get_min_order_qty(self):
        return self.min_order_qty or (self.extra or {}).get("min_order_qty")