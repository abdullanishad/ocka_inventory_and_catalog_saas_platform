# orders/views.py

from __future__ import annotations

import csv
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, Tuple

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.crypto import get_random_string
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import ListView

from accounts.models import Organization
from catalog.models import Product
from .models import Order, OrderItem


# ----- constants & helpers -----

DATE_PRESETS: Dict[str, callable] = {
    "this_week": lambda today: (today - timedelta(days=today.weekday()), today),
    "last_week": lambda today: (
        today - timedelta(days=today.weekday() + 7),
        today - timedelta(days=today.weekday() + 1),
    ),
    "this_month": lambda today: (today.replace(day=1), today),
    "last_30": lambda today: (today - timedelta(days=30), today),
    "all": lambda today: (None, None),
}

def _new_order_number() -> str:
    return "ORD-" + get_random_string(6).upper()

def _date_range_from_params(date_preset: str, start: str | None, end: str | None):
    today = date.today()
    if start or end:
        return (parse_date(start) if start else None, parse_date(end) if end else None)
    return DATE_PRESETS.get(date_preset, DATE_PRESETS["this_week"])(today)


# ----- LIST VIEW -----

class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = "orders/order_list.html"
    paginate_by = 20
    context_object_name = "orders"

    def _filter_by_role(self, qs):
        user = self.request.user
        org = getattr(user, "organization", None)
        if user.is_staff or user.is_superuser:
            return qs
        if not org:
            return qs.none()
        if getattr(org, "org_type", None) == "wholesaler":
            return qs.filter(wholesaler=org)
        if getattr(org, "org_type", None) == "retailer":
            return qs.filter(retailer=org)
        return qs.none()

    def get_queryset(self):
        qs = Order.objects.select_related("retailer", "wholesaler")
        qs = self._filter_by_role(qs)

        q = self.request.GET.get("q")
        status = self.request.GET.get("status", "all")
        date_preset = self.request.GET.get("date", "this_week")
        start = self.request.GET.get("start")
        end = self.request.GET.get("end")

        if q:
            qs = qs.filter(
                Q(number__icontains=q)
                | Q(retailer__name__icontains=q)
                | Q(retailer__city__icontains=q)
                | Q(wholesaler__name__icontains=q)
                | Q(wholesaler__city__icontains=q)
            )

        if status in {c for c, _ in Order.Status.choices}:
            qs = qs.filter(status=status)

        s, e = _date_range_from_params(date_preset, start, end)
        if s:
            qs = qs.filter(date__gte=s)
        if e:
            qs = qs.filter(date__lte=e)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base = self._filter_by_role(Order.objects.select_related("retailer", "wholesaler"))

        q = self.request.GET.get("q")
        date_preset = self.request.GET.get("date", "this_week")
        start = self.request.GET.get("start")
        end = self.request.GET.get("end")

        if q:
            base = base.filter(
                Q(number__icontains=q)
                | Q(retailer__name__icontains=q)
                | Q(retailer__city__icontains=q)
                | Q(wholesaler__name__icontains_q)
                | Q(wholesaler__city__icontains=q)
            )

        s, e = _date_range_from_params(date_preset, start, end)
        if s:
            base = base.filter(date__gte=s)
        if e:
            base = base.filter(date__lte=e)

        counts = {
            "all": base.count(),
            Order.Status.PENDING: base.filter(status=Order.Status.PENDING).count(),
            Order.Status.CONFIRMED: base.filter(status=Order.Status.CONFIRMED).count(),
            Order.Status.SHIPPED: base.filter(status=Order.Status.SHIPPED).count(),
            Order.Status.DELIVERED: base.filter(status=Order.Status.DELIVERED).count(),
        }

        ctx.update({
            "counts": counts,
            "request_params": self.request.GET,
            "tabs": [
                ("all", "All"),
                (Order.Status.PENDING, "Pending"),
                (Order.Status.CONFIRMED, "Confirmed"),
                (Order.Status.SHIPPED, "Shipped"),
                (Order.Status.DELIVERED, "Delivered"),
            ],
            "active_status": self.request.GET.get("status", "all"),
        })
        return ctx


# ----- EXPORT -----

def export_orders_csv(request):
    view = OrderListView()
    view.request = request
    qs = view.get_queryset()

    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="orders.csv"'
    writer = csv.writer(resp)
    writer.writerow(["Order #", "Date", "Retailer", "Retailer City", "Wholesaler",
                     "Items", "Value", "Payment", "Payment Status", "Status"])
    for o in qs:
        writer.writerow([
            o.number, o.date.isoformat(),
            getattr(o.retailer, "name", ""), getattr(o.retailer, "city", ""),
            getattr(o.wholesaler, "name", ""),
            o.items_count, f"{o.total_value}",
            o.get_payment_method_display(), o.payment_status, o.get_status_display(),
        ])
    return resp


# ----- CREATE (single product) -----

@login_required
def create_order(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    retailer_org = getattr(request.user, "organization", None)
    if not retailer_org or retailer_org.org_type != "retailer":
        messages.error(request, "Only retailers can place orders.")
        return redirect("catalog:product_list")

    order = Order.objects.create(
        number=_new_order_number(),
        retailer=retailer_org,
        wholesaler=product.owner,
        items_count=1,
        total_value=product.wholesale_price,
        payment_method=Order.PaymentMethod.COD,
        payment_status="Unpaid",
        status=Order.Status.PENDING,
    )
    OrderItem.objects.create(order=order, product=product, quantity=1, price=product.wholesale_price)
    messages.success(request, f"Order {order.number} placed successfully.")
    return redirect("orders:detail", pk=order.pk)


# ----- DETAIL -----

@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    org = getattr(request.user, "organization", None)
    if not (request.user.is_staff or request.user.is_superuser):
        if not org or (org != order.retailer and org != order.wholesaler):
            messages.error(request, "You do not have access to this order.")
            return redirect("orders:list")
    return render(request, "orders/order_detail.html", {"order": order})


# ----- CART -----

# orders/views.py
from decimal import Decimal
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt  # not needed if you send CSRF properly
from catalog.models import Product  # adjust import to your app
from .cart import get_cart, add_item, update_quantity, remove_item, item_key

def view_cart(request):
    cart = get_cart(request)
    items = list(cart["items"].values())
    for it in items:
        # format prices for template if you want
        it["price"] = f"{Decimal(str(it['price'])):.2f}"
    ctx = {
        "items": items,
        "total": cart["total_amount"],
    }
    return render(request, "orders/cart.html", ctx)

@require_POST
def add_to_cart(request):
    """
    Expected POST fields:
      product_id (int), quantity (int), price (decimal, optional -> falls back to product.wholesale_price)
      moq_label (str, optional), image_url (optional)
    """
    pid = request.POST.get("product_id")
    qty = request.POST.get("quantity")
    price = request.POST.get("price")
    moq_label = request.POST.get("moq_label")  # "3 pcs | S,M,L | 1:1:1"
    image_url = request.POST.get("image_url")

    if not pid or not qty:
        return HttpResponseBadRequest("product_id and quantity are required")

    product = get_object_or_404(Product, id=pid)
    try:
        qty = int(qty)
        if qty <= 0:
            return HttpResponseBadRequest("quantity must be > 0")
    except ValueError:
        return HttpResponseBadRequest("quantity invalid")

    if price is None or price == "":
        price = product.wholesale_price
    try:
        price = Decimal(str(price))
    except Exception:
        return HttpResponseBadRequest("price invalid")

    add_item(request,
             product=product,
             quantity=qty,
             price=price,
             moq_label=moq_label,
             image_url=image_url or (product.image.url if getattr(product, "image", None) else None))

    # Respond JSON for AJAX
    cart = get_cart(request)
    return JsonResponse({
        "ok": True,
        "total_qty": cart["total_qty"],
        "total_amount": cart["total_amount"],
    })

@require_POST
def update_cart_item(request):
    key = request.POST.get("key")
    qty = request.POST.get("quantity")
    if not key or qty is None:
        return HttpResponseBadRequest("key and quantity required")
    try:
        qty = int(qty)
    except ValueError:
        return HttpResponseBadRequest("quantity invalid")

    from .cart import update_quantity as _update
    cart = _update(request, key, qty)
    return JsonResponse({"ok": True, "total_qty": cart["total_qty"], "total_amount": cart["total_amount"]})

def remove_from_cart(request, key):
    from .cart import remove_item as _remove
    cart = _remove(request, key)
    return redirect("orders:view_cart")

def checkout(request):
    # placeholder
    cart = get_cart(request)
    return render(request, "orders/checkout.html", {"cart": cart})
