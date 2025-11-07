# In abdullanishad/ocka_inventory_and_catalog_saas_platform/ocka_inventory_and_catalog_saas_platform-ba7b91b8be5ddbfe7b8624e9500ed82705a0baab/accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, CustomerProfile, Organization  # <-- Import Organization

class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {"fields": ("username", "email", "password", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "role", "password1", "password2"),
        }),
    )
    list_display = ("username", "email", "role", "is_staff")
    search_fields = ("username", "email")
    ordering = ("username",)

admin.site.register(User, UserAdmin)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    # --- 1. ADD 'business_name' to list_display ---
    list_display = ("user", "business_name", "user_type", "phone", "is_verified")
    list_filter = ("user_type", "is_verified")
    
    # --- 2. MAKE THE BUSINESS NAME SEARCHABLE ---
    search_fields = (
        "user__username", 
        "user__email", 
        "phone", 
        "gstin",
        "user__organization__name"  # <-- Add this line
    )

    # --- 3. DEFINE THE FUNCTION TO GET THE NAME ---
    @admin.display(description='Business Name', ordering='user__organization__name')
    def business_name(self, obj):
        """
        Gets the Organization name from the related User.
        """
        if obj.user and obj.user.organization:
            return obj.user.organization.name
        return "N/A"

# Note: The original file had a stray `}` at the end. I have removed it.