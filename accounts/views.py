# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib import messages

# Consolidate all form and model imports here
from .forms import ComprehensiveSignupForm, CustomerProfileForm
from .models import Organization, CustomerProfile
from catalog.models import Category


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True  # logged-in users skip login page

    def get_success_url(self):
        # ✅ First, honor ?next=
        redirect_url = self.get_redirect_url()
        if redirect_url:
            return redirect_url

        user = self.request.user
        if user.role == "retailer":
            return "/catalog/"
        elif user.role == "wholesaler":
            return "/catalog/dashboard/wholesaler/"
        return "/"  # fallback


def signup(request):
    if request.user.is_authenticated:
        return redirect("home") # Redirect logged-in users away

    if request.method == "POST":
        form = ComprehensiveSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome! Your account has been created successfully.")
            # Redirect to their dashboard or profile page
            if user.role == "wholesaler":
                return redirect("catalog:wholesaler_dashboard")
            else:
                return redirect("catalog:product_list")
    else:
        form = ComprehensiveSignupForm()

    return render(request, "accounts/signup.html", {"form": form})


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