# accounts/forms.py
from django import forms
from django.db import transaction
from .models import User, Organization, CustomerProfile

class ComprehensiveSignupForm(forms.Form):
    business_name = forms.CharField(max_length=200, required=True)
    business_type = forms.ChoiceField(choices=Organization.ORG_TYPES, widget=forms.RadioSelect, required=True)
    phone_number = forms.CharField(max_length=20, required=True)
    
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    password_confirm = forms.CharField(widget=forms.PasswordInput, required=True, label="Confirm Password")

    shipping_address = forms.CharField(widget=forms.Textarea, required=False)
    bank_account_holder_name = forms.CharField(max_length=100, required=False)
    bank_account_number = forms.CharField(max_length=30, required=False)
    bank_ifsc_code = forms.CharField(max_length=20, required=False)
    
    terms = forms.BooleanField(required=True, error_messages={'required': 'You must agree to the terms.'})

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password') != cleaned_data.get('password_confirm'):
            raise forms.ValidationError("Passwords do not match.")
        if User.objects.filter(email=cleaned_data.get('email')).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return cleaned_data

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        
        organization = Organization.objects.create(
            name=data['business_name'],
            org_type=data['business_type']
        )
        
        user = User.objects.create_user(
            username=data['email'],
            email=data['email'],
            password=data['password'],
            role=data['business_type'],
            organization=organization
        )
        
        CustomerProfile.objects.filter(user=user).update(
            phone=data['phone_number'],
            street_address=data['shipping_address'],
            bank_account_holder_name=data['bank_account_holder_name'],
            bank_account_number=data['bank_account_number'],
            bank_ifsc_code=data['bank_ifsc_code']
        )
        
        return user


# === ADD THIS CLASS BACK INTO THE FILE ===
class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = CustomerProfile
        fields = (
            'business_logo', 'about_us', 'year_established',
            'phone', 'whatsapp_number', 'website', 'instagram_link',
            'street_address', 'city', 'state', 'pincode',
            'gstin',
            'bank_account_holder_name', 'bank_name', 
            'bank_account_number', 'bank_ifsc_code'
        )
        widgets = {
            'about_us': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'w-full border border-gray-300 rounded-lg px-3 py-2 mt-1'