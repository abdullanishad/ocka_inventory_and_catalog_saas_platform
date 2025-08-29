from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    CustomLoginView,
    signup,
    retailer_dashboard,
    wholesaler_dashboard,
)

app_name = "accounts"

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),  # ✅ added logout
    path("signup/", signup, name="signup"),
    path("retailer-dashboard/", retailer_dashboard, name="retailer_dashboard"),
    path("wholesaler-dashboard/", wholesaler_dashboard, name="wholesaler_dashboard"),
]
