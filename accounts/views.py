# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.db import transaction

# Updated form imports
from .forms import (
    SignupStep1Form, SignupStep2Form, SignupStep3Form, CustomerProfileForm
)
from .models import User, Organization, CustomerProfile
from catalog.models import Category


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        redirect_url = self.get_redirect_url()
        if redirect_url:
            return redirect_url
        user = self.request.user
        if user.role == "retailer":
            return "/catalog/"
        elif user.role == "wholesaler":
            return "/catalog/dashboard/wholesaler/"
        return "/"


# --- NEW MULTI-STEP SIGNUP VIEW ---
@transaction.atomic
def signup(request):
    step = request.GET.get('step', '1')
    signup_data = request.session.get('signup_data', {})

    if request.user.is_authenticated:
        return redirect("home")

    # If a user tries to access a later step without completing the first one
    if step != '1' and not signup_data.get('business_name'):
        return redirect('accounts:signup')

    if step == '1':
        form_class = SignupStep1Form
        template_name = 'accounts/signup_step1.html'
    elif step == '2':
        form_class = SignupStep2Form
        template_name = 'accounts/signup_step2.html'
    elif step == '3':
        form_class = SignupStep3Form
        template_name = 'accounts/signup_step3.html'
    else:
        # Invalid step, redirect to start
        return redirect('accounts:signup')

    if request.method == 'POST':
        # Special handling for step 2 to dynamically show/hide delivery fields
        if step == '2' and signup_data.get('business_type') != 'wholesaler':
            # If not a wholesaler, we don't need to validate delivery fields
            form = SignupStep2Form(request.POST)
            form.fields['supports_doorstep'].required = False
            form.fields['supports_hub'].required = False
        else:
            form = form_class(request.POST)

        if form.is_valid():
            signup_data.update(form.cleaned_data)
            request.session['signup_data'] = signup_data

            if step == '3' or request.POST.get('skip'):
                # Final step or skip: Create the user and profile
                data = request.session.pop('signup_data', {})
                
                organization = Organization.objects.create(
                    name=data['business_name'],
                    org_type=data['business_type']
                )
                
                user = User.objects.create_user(
                    username=data['phone_number'],
                    email=data.get('email', ''),
                    password=data['password'],
                    role=data['business_type'],
                    organization=organization
                )
                
                # Update CustomerProfile with all collected data
                profile_data = {
                    'phone': data.get('phone_number', ''),
                    'street_address': data.get('shipping_address', ''),
                    'bank_account_holder_name': data.get('bank_account_holder_name', ''),
                    'bank_account_number': data.get('bank_account_number', ''),
                    'bank_ifsc_code': data.get('bank_ifsc_code', '')
                }
                # Add delivery options only if they exist in the data (for wholesalers)
                if 'supports_doorstep' in data:
                    profile_data['supports_doorstep'] = data['supports_doorstep']
                if 'supports_hub' in data:
                    profile_data['supports_hub'] = data['supports_hub']
                
                CustomerProfile.objects.filter(user=user).update(**profile_data)
                
                # Set the backend attribute on the user object before logging in
                user.backend = 'accounts.backends.PhoneBackend'
                login(request, user)
                
                messages.success(request, "Welcome! Your account has been created successfully.")
                
                if user.role == "wholesaler":
                    return redirect("catalog:wholesaler_dashboard")
                else:
                    return redirect("catalog:product_list")

            else:
                # Go to the next step
                next_step = int(step) + 1
                return redirect(f"{reverse('accounts:signup')}?step={next_step}")
    else:
        # Pre-populate form with session data if user goes back
        initial_data = signup_data.copy()
        # Handle the ?type=wholesaler query parameter for the "Sell" link
        if step == '1' and not initial_data:
            if request.GET.get('type') == 'wholesaler':
                initial_data['business_type'] = 'wholesaler'
        form = form_class(initial=initial_data)

    # Pass business_type to step 2 template to conditionally show delivery options
    context = {'form': form, 'step': step}
    if step == '2':
        context['business_type'] = signup_data.get('business_type')

    return render(request, template_name, context)

# ... (rest of the views remain the same)

@login_required
def retailer_dashboard(request):
    wholesalers = Organization.objects.filter(org_type="wholesaler")
    categories = Category.objects.all()

    return render(request, "catalog/retailer_dashboard.html", {
        "wholesalers": wholesalers,
        "categories": categories,
    })


@login_required
def wholesaler_dashboard(request):
    return render(request, "catalog/wholesaler_dashboard.html")


@login_required
def profile(request):
    return render(request, "accounts/profile.html")


@login_required
def edit_profile(request):
    # Get the user's profile, or create one if it doesn't exist
    profile, created = CustomerProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = CustomerProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('accounts:profile')
    else:
        form = CustomerProfileForm(instance=profile)

    return render(request, 'accounts/edit_profile.html', {'form': form})