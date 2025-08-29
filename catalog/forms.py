# catalog/forms.py
from django import forms
from django.forms import inlineformset_factory
from .models import Product, SizeStock, Fabric, Color, ProductImage

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        # sku is auto; don't expose it in the form
        fields = [
            "owner",
            "name",
            "image",
            "category",
            "wholesale_price",
            "retail_price",
            "description",
            "fabric",
            "colors",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

# Per-size inventory formset (multiple quantities per size)
SizeStockFormSet = inlineformset_factory(
    Product,
    SizeStock,
    fields=["size", "quantity", "batch_ref"],
    extra=1,
    can_delete=True,
)

# Optional gallery images formset
ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    fields=["image", "alt_text", "position"],
    extra=1,
    can_delete=True,
)
