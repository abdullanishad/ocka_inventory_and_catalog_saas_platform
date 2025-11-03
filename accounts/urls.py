from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    CustomLoginView,
    signup,
    retailer_dashboard,
    wholesaler_dashboard,
    profile, # <--- Import the new profile view
    edit_profile,
    send_otp_view  # <-- IMPORT THE NEW VIEW
)

app_name = "accounts"

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),  # ✅ added logout
    path("signup/", signup, name="signup"),
    # --- ADD THIS NEW URL ---
    path("send-otp/", send_otp_view, name="send_otp"),

    path("retailer-dashboard/", retailer_dashboard, name="retailer_dashboard"),
    path("wholesaler-dashboard/", wholesaler_dashboard, name="wholesaler_dashboard"),
    # === ADD THIS NEW URL PATTERN ===
    path("profile/", profile, name="profile"),

    path("profile/", profile, name="profile"),
    path("profile/edit/", edit_profile, name="edit_profile"), # <-- Add this line
]
