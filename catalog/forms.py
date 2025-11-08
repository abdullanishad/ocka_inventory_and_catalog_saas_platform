# In abdullanishad/ocka_inventory_and_catalog_saas_platform/ocka_inventory_and_catalog_saas_platform-ba7b91b8be5ddbfe7b8624e9500ed82705a0baab/catalog/forms.py

from django import forms
from .models import Product, Category, Color, Size  # Make sure Category, Color, Size are imported

class ProductForm(forms.ModelForm):
    # ... (Your existing ProductForm is unchanged) ...
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
            "fabrics": forms.CheckboxSelectMultiple,
            "colors": forms.CheckboxSelectMultiple,
        }

# --- REPLACE YOUR ProductFilterForm WITH THIS ---

SORT_CHOICES = (
    ("newest", "Newest First"),
    ("price_asc", "Price: Low to High"),
    ("price_desc", "Price: High to Low"),
)

class ProductFilterForm(forms.Form):
    # 1. Set base querysets to .none()
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    colors = forms.ModelMultipleChoiceField(
        queryset=Color.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    sizes = forms.ModelMultipleChoiceField(
        queryset=Size.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    min_price = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Min'})
    )
    max_price = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Max'})
    )
    sort = forms.ChoiceField(
        choices=SORT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'w-full border rounded-lg px-3 py-2'})
    )

    # 2. Add __init__ to accept dynamic querysets
    def __init__(self, *args, **kwargs):
        categories_qs = kwargs.pop('categories_qs', Category.objects.none())
        colors_qs = kwargs.pop('colors_qs', Color.objects.none())
        sizes_qs = kwargs.pop('sizes_qs', Size.objects.none())
        
        super().__init__(*args, **kwargs)
        
        # 3. Assign the dynamic querysets to the form fields
        self.fields['categories'].queryset = categories_qs
        self.fields['colors'].queryset = colors_qs
        self.fields['sizes'].queryset = sizes_qs
        
        # Apply Tailwind classes to price fields
        for field_name, field in self.fields.items():
            if field.widget.__class__ == forms.NumberInput:
                 field.widget.attrs.update({'class': 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm'})