# orders/models.py
from django.db import models
from django.utils import timezone

from accounts.models import Organization
from catalog.models import Product


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"

    class PaymentMethod(models.TextChoices):
        COD = "cod", "COD"
        UPI = "upi", "UPI"
        LINK = "link", "Link"
        CARD = "card", "Card"
        BANK = "bank", "Bank Transfer"

    number = models.CharField(max_length=20, unique=True)  # e.g., ORD-AB12CD
    date = models.DateField(default=timezone.now)

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

    items_count = models.PositiveIntegerField(default=0)
    total_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.COD
    )
    payment_status = models.CharField(
        max_length=20, default="Unpaid", help_text="Free text label for the table"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

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


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
