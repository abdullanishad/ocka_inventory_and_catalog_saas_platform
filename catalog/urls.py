from django.urls import path
from . import views

app_name = "catalog"

urlpatterns = [
    # Public / retailer-facing
    path("", views.product_list, name="product_list"),
    path("home/", views.home, name="home"),
    path("product/<int:pk>/", views.product_detail, name="product_detail"),
    path("product/<int:pk>/related/", views.related_products, name="related_products"),

    # Dashboards
    path("dashboard/wholesaler/", views.wholesaler_dashboard, name="wholesaler_dashboard"),
    path("dashboard/retailer/", views.retailer_dashboard, name="retailer_dashboard"),

    # Stock management
    path("stock/<int:product_id>/adjust/", views.adjust_stock, name="adjust_stock"),

    # Product CRUD (inline table is main; keep single product edit)
    path("products/new/", views.product_edit, name="product_new"),
    path("products/<int:pk>/edit/", views.product_edit, name="product_edit"),
]
