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
