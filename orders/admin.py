# orders/admin.py
from django.contrib import admin
from .models import Order

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("number", "date", "retailer", "items_count", "total_value", "payment_method", "status")
    search_fields = ("number", "retailer__name", "retailer__city")
    list_filter = ("status", "payment_method", "date")

