# orders/forms.py
from django import forms
from .models import Shipment

class ShipmentForm(forms.ModelForm):
    class Meta:
        model = Shipment
        fields = ['tracking_id', 'courier_name', 'shipping_document']
        widgets = {
            'tracking_id': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2'}),
            'courier_name': forms.TextInput(attrs={'class': 'w-full border rounded-lg px-3 py-2'}),
            'shipping_document': forms.FileInput(attrs={'class': 'w-full'}),
        }