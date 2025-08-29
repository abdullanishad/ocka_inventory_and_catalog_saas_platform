from django.contrib import admin
from .models import (
    Product, ProductImage,
    Category, Size, CategorySize, SizeStock,
    Fabric, Color,
)

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "alt_text", "position")
    ordering = ("position", "id")

class SizeStockInline(admin.TabularInline):
    model = SizeStock
    extra = 1
    fields = ("size", "quantity", "batch_ref")
    ordering = ("size__name", "id")

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "owner", "category", "wholesale_price", "retail_price")
    list_filter = ("category", "owner")
    search_fields = ("name", "sku")
    inlines = [ProductImageInline, SizeStockInline]

admin.site.register(Category)
admin.site.register(Size)
admin.site.register(CategorySize)
admin.site.register(Fabric)
admin.site.register(Color)
