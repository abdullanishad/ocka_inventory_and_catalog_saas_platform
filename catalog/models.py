# catalog/models.py
from __future__ import annotations
from dataclasses import dataclass
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
        ordering = ["name"]  # just alphabetical as fallback

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

    # Auto SKU (see save())
    sku = models.CharField(max_length=32, unique=True, blank=True)

    category = models.ForeignKey(Category, on_delete=models.PROTECT, null=False, blank=False)
    wholesale_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(1)])
    retail_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(1)])

    description = models.TextField(blank=True)
    fabric = models.ForeignKey(Fabric, null=True, blank=True, on_delete=models.SET_NULL, related_name="products")
    colors = models.ManyToManyField(Color, blank=True, related_name="products")

    # Optional extra gallery (primary image is 'image')
    def primary_image_url(self):
        if self.image:
            return self.image.url
        first = self.images.order_by("position", "id").first()
        return first.image.url if first else ""

    # ---- SKU generation ----


    def save(self, *args, **kwargs):
        if not self.sku:
            owner_code = slugify(self.owner.name)[:3].upper() if hasattr(self.owner, "name") else "OWN"
            cat_code = (self.category.code or slugify(self.category.name)[:4].upper()) if self.category_id else "CAT"

            # find the last sequence used for this owner + category
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

    # @property
    # def size_stock_totals(self) -> Dict[int, Tuple[str, int]]:
    #     """
    #     Returns {1: ('S', 3), 2: ('M', 5)} where key = Size.id
    #     """
    #     if not self.pk:
    #         return {}

    #     out: Dict[int, int] = {}
    #     for row in self.size_stocks.select_related("size"):
    #         out[row.size.id] = out.get(row.size.id, 0) + row.quantity

    #     # keep order from CategorySize if available
    #     ordered = {}
    #     mapping = CategorySize.objects.filter(category=self.category).select_related("size") if self.category_id else []
    #     if mapping:
    #         for m in mapping:
    #             ordered[m.size.id] = (m.size.name, out.get(m.size.id, 0))
    #     # include ad-hoc sizes
    #     for sid, qty in out.items():
    #         if sid not in ordered:
    #             size = Size.objects.get(id=sid)
    #             ordered[sid] = (size.name, qty)

    #     return ordered

    @property
    def size_stock_totals(self) -> Dict[int, int]:
        """
        Returns {1: 5, 2: 10} mapping size_id → quantity.
        """
        if not self.pk:
            return {}

        out: Dict[int, int] = {}
        for row in self.size_stocks.select_related("size"):
            out[row.size.name] = out.get(row.size.name, 0) + row.quantity

        return out
    
    @property
    def size_stock_display(self):
        """
        Returns { "S": 5, "M": 10, "L": 2 }
        """
        if not self.pk:
            return {}

        out = {}
        for row in self.size_stocks.select_related("size"):
            out[row.size.name] = out.get(row.size.name, 0) + row.quantity

        # Add missing category sizes with 0
        mapping = CategorySize.objects.filter(category=self.category).select_related("size") if self.category_id else []
        for m in mapping:
            if m.size.name not in out:
                out[m.size.name] = 0

        return out




    @property
    def total_stock(self) -> int:
        return sum(self.size_stock_totals.values()) if self.pk else 0




    def available_ratios_and_moq(self) -> List[Tuple[str, int]]:
        """
        Compute nice, human ratios based on current stock.
        Returns list of (ratio_str, moq_total). Examples:
        [('1:1:1', 3), ('1:2:2', 5), ('1:1:1:1', 4)]
        Strategy:
        - Use sizes that have stock > 0
        - R1: equal 1-per-size across all stocked sizes  -> '1:1:...'
        - R2: min-scaled ratio (each qty // min_qty, floor to >=1) -> simple like '1:2:2'
        - R3: if >=4 sizes stocked, also add strict equal across first 4 -> '1:1:1:1'
        - De-duplicate and keep in ascending MOQ order
        """
        stock = self.size_stock_totals  # ordered
        sizes = [k for k, v in stock.items() if v > 0]
        if not sizes:
            return []

        # quantities in order
        q = [stock[s] for s in sizes]
        mn = min(q)

        # Ratio 1: equal 1 each for all in-stock sizes (limited by having >=1)
        r_equal_all = ":".join(["1"] * len(sizes))
        moq_equal_all = len(sizes)

        # Ratio 2: proportional by min
        # e.g. [3,4,4] -> base [1, ceil(4/2), ceil(4/2)]? We'll keep it simple: round up to nearest integer when min < 3
        # Better: divide by mn and round to nearest int not exceeding available when multiplied by mn.
        prop = []
        for n in q:
            v = max(1, round(n / mn))
            prop.append(str(v))
        r_prop = ":".join(prop)
        moq_prop = sum(int(x) for x in prop)

        # Ratio 3: if 4+ sizes → strict 1 for first 4 (classic set packing)
        r_four = None
        moq_four = None
        if len(sizes) >= 4:
            r_four = "1:1:1:1"
            moq_four = 4

        # Build list, unique by ratio string, sort by moq asc
        opts = {(r_equal_all, moq_equal_all), (r_prop, moq_prop)}
        if r_four:
            opts.add((r_four, moq_four))
        # Filter options that are actually fulfillable (we must be able to build at least one set)
        valid = []
        for ratio, moq in opts:
            if can_fulfill_ratio(q, [int(x) for x in ratio.split(":")]):
                valid.append((ratio, moq))
        valid.sort(key=lambda x: x[1])
        return valid
    
    def initial_size_stocks(self) -> List[Dict[str, int]]:
        """
        Returns a list of dicts suitable for prefilling a formset:
        [{'size': <Size>, 'quantity': 5}, ...]
        It ensures all sizes from the product's category are included,
        even if not yet present in DB.
        """
        rows = []
        existing = {s.size_id: s for s in self.size_stocks.all()}
        mapping = CategorySize.objects.filter(category=self.category).select_related("size") if self.category_id else []

        for m in mapping:
            if m.size_id in existing:
                rows.append({"size": m.size, "quantity": existing[m.size_id].quantity})
            else:
                rows.append({"size": m.size, "quantity": 0})

        # Also include any extra/ad-hoc size rows not mapped in CategorySize
        for s in existing.values():
            if not mapping.filter(size_id=s.size_id).exists():
                rows.append({"size": s.size, "quantity": s.quantity})

        return rows



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
    """
    Per-size inventory rows (supports multiple batches per size).
    Example: size 'M' can have several rows: 5 pcs + 3 pcs, etc.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="size_stocks")
    size = models.ForeignKey(Size, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    batch_ref = models.CharField(max_length=40, blank=True, help_text="Optional batch/lot reference")

    class Meta:
        ordering = ["size__name", "id"]

    def __str__(self):
        return f"{self.product.sku} - {self.size.name}: {self.quantity}"


# ---------- Helpers used by Product.available_ratios_and_moq ----------
def can_fulfill_ratio(q_list: List[int], ratio: List[int]) -> bool:
    """
    Given quantities per size and a ratio vector (same length or prefix),
    check if at least ONE pack can be assembled.
    If ratio has fewer entries than sizes, we use the first len(ratio) sizes.
    """
    n = min(len(q_list), len(ratio))
    if n == 0: return False
    q = q_list[:n]
    r = ratio[:n]
    # One pack possible if every size can give r[i] units
    return all(q[i] >= r[i] for i in range(n))
