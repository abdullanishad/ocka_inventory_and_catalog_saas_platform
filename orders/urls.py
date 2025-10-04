from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    # Order listing + export
    path("", views.OrderListView.as_view(), name="list"),
    path("export/", views.export_orders_csv, name="export"),

    # Create a one-click order for a single product
    path("create/<int:product_id>/", views.create_order, name="create"),

    # Cart (session-based, single-wholesaler)
    path("cart/", views.view_cart, name="view_cart"),
    path("cart/add/", views.add_to_cart, name="add_to_cart"),
    path("cart/update/", views.update_cart_item, name="update_cart_item"),  # optional
    path("cart/remove/<str:key>/", views.remove_from_cart, name="remove_from_cart"),  # optional
    path("checkout/", views.checkout, name="checkout"),  # stub

    # Detail
    path("<int:pk>/", views.order_detail, name="detail"),
    path("ajax-checkout/", views.ajax_checkout, name="ajax_checkout"),
    path('update-status/<int:pk>/', views.update_status, name='update_status'),
    path("cancel/<int:pk>/", views.cancel_order, name="cancel"),

    path('<int:pk>/start-payment/', views.start_payment, name='start_payment'),
    path('payment-success/', views.payment_success, name='payment_success'),

]
