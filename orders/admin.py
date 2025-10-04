# orders/admin.py
from django.contrib import admin, messages
from .models import Order
from .services import release_payment_to_wholesaler # <-- Import the function

@admin.action(description="Release payment to Wholesaler")
def release_payment_action(modeladmin, request, queryset):
    """
    This is the function that will run when you select the action in the admin.
    """
    # We only want to process orders that are in the SHIPPED state
    eligible_orders = queryset.filter(status=Order.Status.SHIPPED)
    
    success_count = 0
    error_count = 0

    if not eligible_orders.exists():
        modeladmin.message_user(request, "No selected orders were in the 'Shipped' status to process.", messages.WARNING)
        return

    for order in eligible_orders:
        success, message = release_payment_to_wholesaler(order)
        if success:
            success_count += 1
        else:
            error_count += 1
            modeladmin.message_user(request, message, messages.ERROR)

    if success_count > 0:
        modeladmin.message_user(request, f"Successfully released payment for {success_count} order(s).", messages.SUCCESS)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("number", "date", "retailer", "wholesaler", "total_value", "status")
    search_fields = ("number", "retailer__name", "wholesaler__name")
    list_filter = ("status", "payment_method", "date")
    
    # === ADD THE CUSTOM ACTION TO YOUR ORDER ADMIN ===
    actions = [release_payment_action]