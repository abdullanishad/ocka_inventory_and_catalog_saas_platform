# catalog/models.py
from __future__ import annotations
from typing import List, Tuple, Dict

from django.db import models
from django.core.validators import MinValueValidator
from django.utils.text import slugify

from accounts.models import Organization
from django.db.models import Max


# ---------- Reference tables ----------
class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(
        max_length=6, blank=True,
        help_text="Short code used in SKU (auto if blank, e.g. PANT/SHRT).",
        default=""
    )

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = slugify(self.name)[:6].upper()
        super().save(*args, **kwargs)

    def __str__(self): return self.name


class Size(models.Model):
    """Master size list (XS,S,M,28,30,Free, etc.)."""
    name = models.CharField(max_length=20, unique=True)
    class Meta:
        ordering = ["name"]
    def __str__(self):
        return self.name


class CategorySize(models.Model):
    """Map which sizes belong to a category, and in what order."""
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="category_sizes"
    )
    size = models.ForeignKey(Size, on_delete=models.PROTECT)
    order = models.PositiveIntegerField(default=0)
    class Meta:
        unique_together = [("category", "size")]
        ordering = ["order", "size__name"]
    def __str__(self):
        return f"{self.category.name} – {self.size.name}"


class Fabric(models.Model):
    name = models.CharField(max_length=60, unique=True)
    def __str__(self): return self.name


class Color(models.Model):
    name = models.CharField(max_length=40, unique=True)
    def __str__(self): return self.name


# ---------- UPDATED MOQ MODEL ----------
class MoqOption(models.Model):
    """A specific MOQ option defined by a wholesaler for a product."""
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name="moq_options")
    configuration = models.JSONField(default=dict)
    
    class Meta:
        ordering = ['id']

    @property
    def total_quantity(self) -> int:
        """Calculates the total number of items in the pack."""
        return sum(self.configuration.values())

    @property
    def sizes_str(self) -> str:
        """Returns the sizes as a string, e.g., 'S, M, L'."""
        return ", ".join(self.configuration.keys())

    @property
    def ratio_str(self) -> str:
        """Returns the ratio as a string, e.g., '1:2:1'."""
        return ":".join(str(v) for v in self.configuration.values())

    @property
    def display_label(self) -> str:
        """Generates the full label for the cart, e.g., '4 pcs | S, M, L | 1:2:1'."""
        if not self.configuration:
            return ""
        return f"{self.total_quantity} pcs | {self.sizes_str} | {self.ratio_str}"

    def __str__(self):
        return f"{self.product.name} - {self.display_label}"

    def to_tuple(self):
        """Helper method to mimic the old format for the product detail page."""
        return (self.display_label, self.total_quantity, self.id)


# ---------- Product & inventory ----------
class Product(models.Model):
    owner = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="products",
        limit_choices_to={"org_type": "wholesaler"},
    )
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to="product_images/", blank=True, null=True)
    sku = models.CharField(max_length=32, unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, null=False, blank=False)
    wholesale_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(1)])
    retail_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(1)])
    description = models.TextField(blank=True)
    # === UPDATED THIS FIELD ===
    fabrics = models.ManyToManyField('Fabric', blank=True, related_name="products")
    colors = models.ManyToManyField(Color, blank=True, related_name="products")
    is_active = models.BooleanField(default=True)


    def primary_image_url(self):
        if self.image:
            return self.image.url
        first = self.images.order_by("position", "id").first()
        return first.image.url if first else ""

    def save(self, *args, **kwargs):
        if not self.sku:
            owner_code = slugify(self.owner.name)[:3].upper() if hasattr(self.owner, "name") else "OWN"
            cat_code = (self.category.code or slugify(self.category.name)[:4].upper()) if self.category_id else "CAT"
            last_sku = (
                Product.objects
                .filter(owner=self.owner, category=self.category, sku__startswith=f"{owner_code}-{cat_code}-")
                .aggregate(Max("sku"))
            )["sku__max"]
            if last_sku:
                try:
                    seq = int(last_sku.split("-")[-1]) + 1
                except ValueError:
                    seq = 1
            else:
                seq = 1
            self.sku = f"{owner_code}-{cat_code}-{seq:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def size_stock_totals(self) -> Dict[str, int]:
        if not self.pk:
            return {}
        out: Dict[str, int] = {}
        for row in self.size_stocks.select_related("size"):
            out[row.size.name] = out.get(row.size.name, 0) + row.quantity
        return out

    @property
    def size_stock_display(self):
        if not self.pk:
            return {}
        out = {}
        for row in self.size_stocks.select_related("size"):
            out[row.size.name] = out.get(row.size.name, 0) + row.quantity
        mapping = CategorySize.objects.filter(category=self.category).select_related("size") if self.category_id else []
        for m in mapping:
            if m.size.name not in out:
                out[m.size.name] = 0
        return out

    @property
    def total_stock(self) -> int:
        """Total stock across all sizes."""
        return sum(self.size_stock_totals.values()) if self.pk else 0

    # ========== NEW METHOD TO CHECK STOCK FOR MOQ OPTIONS ==========
    @property
    def available_moq_options(self):
        """
        Filters the defined MOQ options and returns only those
        that can be fulfilled with the current stock.
        """
        available_options = []
        current_stock = self.size_stock_display
        
        for option in self.moq_options.all():
            is_available = True
            # Check if there is enough stock for each size in the pack configuration
            for size_name, required_qty in option.configuration.items():
                if current_stock.get(size_name, 0) < required_qty:
                    is_available = False
                    break # Not enough stock for this size, so the pack is unavailable
            
            if is_available:
                available_options.append(option)
                
        return available_options

    # The available_ratios_and_moq method is now replaced by a simple property
    @property
    def moq_display_options(self) -> list:
        """Returns a list of tuples for the product detail page."""
        return [
            (f"{opt.total_quantity} pcs | {', '.join(opt.configuration.keys())} | {':'.join(map(str, opt.configuration.values()))}", opt.total_quantity, opt.id)
            for opt in self.moq_options.all()
        ]

    def get_moq_options(self) -> List[Tuple[str, int]]:
        """Returns a list of manually defined MOQ options."""
        return [option.to_tuple() for option in self.moq_options.all()]


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="product_images/")
    alt_text = models.CharField(max_length=200, blank=True)
    position = models.PositiveIntegerField(default=0)
    class Meta:
        ordering = ["position", "id"]
    def __str__(self):
        return f"{self.product.sku} – {self.id}"


class SizeStock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="size_stocks")
    size = models.ForeignKey(Size, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    batch_ref = models.CharField(max_length=40, blank=True, help_text="Optional batch/lot reference")
    class Meta:
        ordering = ["size__name", "id"]
    def __str__(self):
        return f"{self.product.sku} - {self.size.name}: {self.quantity}"


# ... (Hero and TopBrand models remain the same) ...
class Hero(models.Model):
    title = models.CharField(max_length=140, default="Welcome to Ocka")
    subtitle = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to="homepage/hero/")
    cta_text = models.CharField(max_length=80, blank=True, default="Shop Now")
    cta_url = models.CharField(max_length=255, blank=True, default="#")
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['order', '-created_at']
    def __str__(self):
        return f"Hero: {self.title} ({'active' if self.is_active else 'inactive'})"


class TopBrand(models.Model):
    name = models.CharField(max_length=120)
    logo = models.ImageField(upload_to="homepage/brands/")
    link = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)
    class Meta:
        ordering = ['order']
    def __str__(self):
        return self.name