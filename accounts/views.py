# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from .forms import CustomUserCreationForm
from .models import Organization
from catalog.models import Category


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True  # logged-in users skip login page

    def get_success_url(self):
        user = self.request.user
        if user.role == "retailer":
            return "/accounts/retailer-dashboard/"
        elif user.role == "wholesaler":
            return "/accounts/wholesaler-dashboard/"
        return "/"  # fallback


def signup(request):
    # redirect if already logged in
    if request.user.is_authenticated:
        if request.user.role == "retailer":
            return redirect("catalog:retailer_dashboard")
        elif request.user.role == "wholesaler":
            return redirect("catalog:wholesaler_dashboard")
        else:
            return redirect("/")  # fallback

    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)

            # ✅ create or assign organization automatically
            if user.role == "wholesaler":
                org, _ = Organization.objects.get_or_create(
                    name=f"{user.username}'s Org", org_type="wholesaler"
                )
            else:  # default retailer
                org, _ = Organization.objects.get_or_create(
                    name=f"{user.username}'s Org", org_type="retailer"
                )

            user.organization = org
            user.save()

            login(request, user)

            if user.role == "retailer":
                return redirect("catalog:retailer_dashboard")
            elif user.role == "wholesaler":
                return redirect("catalog:wholesaler_dashboard")
    else:
        form = CustomUserCreationForm()

    return render(request, "accounts/signup.html", {"form": form})


from .models import Organization
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
