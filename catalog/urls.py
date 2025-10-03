from django.urls import path
from . import views

app_name = "catalog"

urlpatterns = [
    # Public / retailer-facing
    path("", views.product_list, name="product_list"),
    path("home/", views.home, name="home"),
    path("product/<int:pk>/", views.product_detail, name="product_detail"),

    # Dashboards
    path("dashboard/wholesaler/", views.wholesaler_dashboard, name="wholesaler_dashboard"),


    # Product CRUD (inline table is main; keep single product edit)
    path("product/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("product/add/", views.product_add, name="product_add"),
    path("category/<int:category_id>/sizes/", views.category_sizes, name="category_sizes"),

    path("product-image/<int:pk>/delete/", views.product_image_delete, name="product_image_delete"),
    
     # === ADD THIS NEW URL PATTERN ===
    path("product/<int:pk>/delete/", views.delete_product, name="delete_product"),

    path("reports/", views.wholesale_reports, name="reports"),
    path("reports/export/csv/", views.reports_export_csv, name="reports_export_csv"),
]
