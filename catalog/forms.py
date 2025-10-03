# catalog/forms.py
from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "image",
            "category",
            "wholesale_price",
            "retail_price",
            "description",
            "fabrics",
            "colors",
        ]
        widgets = {
            "name": forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2'}),
            "category": forms.Select(attrs={'class': 'w-full border rounded-lg px-3 py-2'}),
            "wholesale_price": forms.NumberInput(attrs={'class': 'w-full border rounded-lg px-3 py-2'}),
            "retail_price": forms.NumberInput(attrs={'class': 'w-full border rounded-lg px-3 py-2'}),
            "description": forms.Textarea(attrs={"rows": 4, 'class': 'w-full border rounded-lg px-3 py-2'}),
            "fabric": forms.Select(attrs={'class': 'w-full border rounded-lg px-3 py-2'}),
             # === WIDGETS FOR CHECKBOXES ===
            "fabrics": forms.CheckboxSelectMultiple,
            "colors": forms.CheckboxSelectMultiple,
        }

#
# The old MoqOptionFormSet that was causing the error has been completely removed.
#