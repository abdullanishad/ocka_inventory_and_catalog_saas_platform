# orders/models.py
from django.db import models
from django.utils import timezone

from accounts.models import Organization
from catalog.models import Product


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Confirmation"
        REJECTED = "REJECTED", "Rejected"
        AWAITING_PAYMENT = "AWAITING_PAYMENT", "Awaiting Payment"
        PAID = "PAID", "Paid (Processing)" # Payment held in Escrow
        SHIPPED = "SHIPPED", "Shipped"
        DELIVERED = "DELIVERED", "Delivered" # Optional, if you track delivery
        COMPLETED = "COMPLETED", "Completed" # Payment released to wholesaler
        CANCELLED = "CANCELLED", "Cancelled"

    class PaymentMethod(models.TextChoices):
        # --- ADD MORE CHOICES ---
        COD = "cod", "COD"
        UPI = "upi", "UPI"
        CARD = "card", "Card"
        NETBANKING = "netbanking", "Netbanking"
        WALLET = "wallet", "Wallet"
        # BANK = "bank", "Bank Transfer" # This is less common via Razorpay gateway

    number = models.CharField(max_length=20, unique=True)  # e.g., ORD-AB12CD
    date = models.DateTimeField(default=timezone.now)

    retailer = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="placed_orders",
        limit_choices_to={"org_type": "retailer"},
    )
    wholesaler = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="received_orders",
        limit_choices_to={"org_type": "wholesaler"},
    )

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Add new fields
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # This field will store the final payable amount
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # --- UPDATE THE payment_method FIELD ---
    payment_method = models.CharField(
        max_length=20, 
        choices=PaymentMethod.choices, 
        blank=True,  # Allow the field to be blank
        null=True    # Allow the database column to be NULL
    )
    payment_status = models.CharField(
        max_length=20, default="Unpaid", help_text="Free text label for the table"
    )
    # === INCREASE MAX_LENGTH FOR STATUS FIELD ===
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)


    # Fields to store Razorpay IDs
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=200, blank=True, null=True)


    class Meta:
        ordering = ["-date", "-id"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["wholesaler"]),
            models.Index(fields=["retailer"]),
        ]

    def __str__(self):
        return self.number
    
    # orders/models.py
# ... (inside the Order model)

    def calculate_totals(self):
        """Calculates the grand total based on other fields."""
        self.grand_total = self.subtotal + self.shipping_charge + self.gst_amount
        self.save()

# ...


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # --- ADD THIS NEW FIELD ---
    pack_details = models.CharField(max_length=100, blank=True, null=True, help_text="Stores the selected pack/MOQ details")


    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

# === ADD THIS NEW MODEL ===
class Shipment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="shipment")
    tracking_id = models.CharField(max_length=100, blank=True, null=True)
    courier_name = models.CharField(max_length=100, blank=True, null=True)
    shipping_document = models.FileField(upload_to="shipping_docs/", blank=True, null=True)
    shipped_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Shipment for Order {self.order.number}"
    

