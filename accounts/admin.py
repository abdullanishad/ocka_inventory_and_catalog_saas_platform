from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

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


from django.contrib import admin
from .models import CustomerProfile, Organization, User  # adjust import path

@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "user_type", "phone", "is_verified")
    list_filter = ("user_type", "is_verified")
    search_fields = ("user__username", "user__email", "phone", "gstin")