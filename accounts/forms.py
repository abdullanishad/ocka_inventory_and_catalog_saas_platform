from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, CustomerProfile


class CustomUserCreationForm(UserCreationForm):
    ROLE_CHOICES = [
        ("retailer", "Retailer"),
        ("wholesaler", "Wholesaler"),
    ]
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect)

    class Meta:
        model = User
        fields = ("username", "email", "role", "password1", "password2")


# === ADD THIS NEW FORM CLASS ===
class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = CustomerProfile
        fields = (
            'business_logo', 'about_us', 'year_established',
            'phone', 'whatsapp_number', 'website', 'instagram_link',
            'street_address', 'city', 'state', 'pincode',
            'gstin'
        )
        widgets = {
            'about_us': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Tailwind classes to all fields
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'w-full border border-gray-300 rounded-lg px-3 py-2 mt-1'