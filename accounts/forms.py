# accounts/forms.py
from django import forms
from .models import User, Organization, CustomerProfile

# Step 1: Core Account Details
class SignupStep1Form(forms.Form):
    business_name = forms.CharField(max_length=200, required=True)
    business_type = forms.ChoiceField(choices=Organization.ORG_TYPES, widget=forms.RadioSelect, required=True)
    phone_number = forms.CharField(max_length=20, required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True, min_length=8)
    password_confirm = forms.CharField(widget=forms.PasswordInput, required=True, label="Confirm Password")
    terms = forms.BooleanField(required=True, error_messages={'required': 'You must agree to the terms.'})

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password') != cleaned_data.get('password_confirm'):
            self.add_error('password_confirm', "Passwords do not match.")
        return cleaned_data

# Step 2: Business Profile & Delivery Options
class SignupStep2Form(forms.Form):
    email = forms.EmailField(required=True)
    shipping_address = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), required=False)
    supports_doorstep = forms.BooleanField(required=False, initial=False, widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'}))
    supports_hub = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'}))

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

# Step 3: Bank Details
class SignupStep3Form(forms.Form):
    bank_account_holder_name = forms.CharField(max_length=100, required=False)
    bank_account_number = forms.CharField(max_length=30, required=False)
    bank_ifsc_code = forms.CharField(max_length=20, required=False)

# Main Customer Profile Form for editing
class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = CustomerProfile
        fields = (
            'business_logo', 'about_us', 'year_established',
            'phone', 'whatsapp_number', 'website', 'instagram_link',
            'street_address', 'city', 'state', 'pincode',
            'gstin',
            'bank_account_holder_name', 'bank_name', 
            'bank_account_number', 'bank_ifsc_code',
            'supports_doorstep', 'supports_hub'
        )
        widgets = {
            'about_us': forms.Textarea(attrs={'rows': 4}),
            'supports_doorstep': forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'}),
            'supports_hub': forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name not in ['supports_doorstep', 'supports_hub']:
                field.widget.attrs['class'] = 'w-full border border-gray-300 rounded-lg px-3 py-2 mt-1'