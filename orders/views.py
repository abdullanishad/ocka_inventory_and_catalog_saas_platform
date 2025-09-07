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

from django.http import JsonResponse, HttpResponseBadRequest
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from django.db.models import Sum, F, Value, DecimalField, IntegerField
from django.db.models.functions import Coalesce

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

# views.py
from django.db.models import Q, Sum, F
from django.db.models.functions import Coalesce
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin


from .models import Order
# adjust import path for your _date_range_from_params helper


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

        # annotate using names that DON'T conflict with model fields
        # items_count (int) and total_value (decimal) need explicit output_field for Coalesce/Sum
        qs = qs.annotate(
            annot_items_count=Coalesce(Sum("items__quantity"), Value(0), output_field=IntegerField()),
            annot_total_value=Coalesce(
                Sum(
                    F("items__quantity") * F("items__price"),
                    output_field=DecimalField(max_digits=18, decimal_places=2),
                ),
                Value(0),
                output_field=DecimalField(max_digits=18, decimal_places=2),
            ),
        )

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

        valid_statuses = {c for c, _ in Order.Status.choices}
        if status in valid_statuses:
            qs = qs.filter(status=status)

        s, e = _date_range_from_params(date_preset, start, end)
        if s:
            qs = qs.filter(date__gte=s)
        if e:
            qs = qs.filter(date__lte=e)
        return qs


    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # pass is_wholesaler so template can render opposite party column
        user = self.request.user
        org = getattr(user, "organization", None)
        is_wholesaler = False
        if user.is_staff or user.is_superuser:
            is_wholesaler = False
        elif org and getattr(org, "org_type", None) == "wholesaler":
            is_wholesaler = True

        # base queryset for counts (apply same role + basic filters as get_queryset)
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
                | Q(wholesaler__name__icontains=q)
                | Q(wholesaler__city__icontains=q)
            )

        s, e = _date_range_from_params(date_preset, start, end)
        if s:
            base = base.filter(date__gte=s)
        if e:
            base = base.filter(date__lte=e)

        # Build counts dynamically from Status.choices
        counts = {"all": base.count()}
        for status_value, _status_label in Order.Status.choices:
            counts[status_value] = base.filter(status=status_value).count()

        # Build tabs from choices (keeps labels in sync)
        tabs = [("all", "All")]
        for status_value, status_label in Order.Status.choices:
            tabs.append((status_value, status_label))

        ctx.update(
            {
                "counts": counts,
                "request_params": self.request.GET,
                "tabs": tabs,
                "active_status": self.request.GET.get("status", "all"),
                "is_wholesaler": is_wholesaler,
            }
        )
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


from decimal import Decimal, InvalidOperation
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

# other imports already present in your file...
# from .models import Order, OrderItem  # assume already imported above

@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)

    # permission check (unchanged)
    org = getattr(request.user, "organization", None)
    if not (request.user.is_staff or request.user.is_superuser):
        if not org or (org != order.retailer and org != order.wholesaler):
            messages.error(request, "You do not have access to this order.")
            return redirect("orders:list")

    # Determine a single "placed at" timestamp that exists on the model
    placed_at = (
        getattr(order, "date", None)
        or getattr(order, "created", None)
        or getattr(order, "created_at", None)
        or getattr(order, "created_on", None)
        or None
    )

    # Load order items in a safe way and compute subtotal per item
    try:
        raw_items_qs = order.items.select_related("product").all()
    except Exception:
        raw_items_qs = order.orderitem_set.select_related("product").all()

    order_items = []
    for oi in raw_items_qs:
        # oi.price might already be Decimal or string or float
        try:
            price = Decimal(str(oi.price))
        except (InvalidOperation, TypeError, ValueError):
            # fallback to 0 if price is not parseable
            price = Decimal("0")
        qty = int(getattr(oi, "quantity", 1) or 0)
        subtotal = price * qty
        order_items.append({
            "obj": oi,              # original OrderItem object (if template needs fields)
            "product": getattr(oi, "product", None),
            "quantity": qty,
            "price": price,
            "subtotal": subtotal,
        })

    # Convenience flags for template (useful for showing role-specific actions)
    user_org = getattr(request.user, "organization", None)
    context = {
        "order": order,
        "placed_at": placed_at,
        "order_items": order_items,
        "is_retailer": bool(user_org and user_org == order.retailer),
        "is_wholesaler": bool(user_org and user_org == order.wholesaler),
        "is_staff": request.user.is_staff or request.user.is_superuser,
    }
    return render(request, "orders/order_detail.html", context)



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

from decimal import Decimal
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string

# assume get_cart, Product, Order, OrderItem, _new_order_number are already imported above

@require_POST
@login_required
def ajax_checkout(request):
    """
    Create one Order per wholesaler found in the session cart.
    Returns JSON:
      { success: True, orders: [{ order_number, order_id, order_url, html, order_total }, ...] }
    Decimal values are converted to strings.
    """
    try:
        cart = get_cart(request)
        raw_items = list(cart.get("items", {}).values())
        if not raw_items:
            return JsonResponse({"success": False, "error": "Cart is empty."}, status=400)

        retailer_org = getattr(request.user, "organization", None)
        if not retailer_org or getattr(retailer_org, "org_type", None) != "retailer":
            return JsonResponse({"success": False, "error": "Only retailers can place orders."}, status=403)

        # Build mapping: wholesaler -> list of item dicts
        wholesaler_map = {}
        prod_cache = {}  # pid -> Product instance

        for it in raw_items:
            pid = it.get("product_id") or it.get("id") or it.get("pk")
            if not pid:
                return JsonResponse({"success": False, "error": "Cart item missing product id."}, status=400)
            # fetch product (cache)
            if pid not in prod_cache:
                try:
                    prod_cache[pid] = Product.objects.select_related("owner").get(pk=pid)
                except Product.DoesNotExist:
                    return JsonResponse({"success": False, "error": f"Product {pid} not found."}, status=400)
            product = prod_cache[pid]
            wholesaler = getattr(product, "owner", None)  # may be None
            key = wholesaler.pk if wholesaler is not None else f"__none__"
            wholesaler_map.setdefault(key, {"wholesaler": wholesaler, "items": []})
            # normalize price and quantity
            qty = int(it.get("quantity", 1))
            price = it.get("price", 0)
            price = Decimal(str(price))
            wholesaler_map[key]["items"].append({
                "product": product,
                "quantity": qty,
                "price": price,
                "raw": it,
            })

        created_orders = []
        # Wrap in atomic so either all orders are created or none
        with transaction.atomic():
            for entry in wholesaler_map.values():
                wholesaler = entry["wholesaler"]
                items = entry["items"]
                # compute totals for this wholesaler
                items_count = sum(i["quantity"] for i in items)
                total_value = sum(i["price"] * i["quantity"] for i in items)

                order = Order.objects.create(
                    number=_new_order_number(),
                    retailer=retailer_org,
                    wholesaler=wholesaler,
                    items_count=items_count,
                    total_value=total_value,
                    payment_method=Order.PaymentMethod.COD,
                    payment_status="Unpaid",
                    status=Order.Status.PENDING,
                )

                # create order items
                for it in items:
                    OrderItem.objects.create(
                        order=order,
                        product=it["product"],
                        quantity=it["quantity"],
                        price=it["price"],
                    )

                # render snippet for this order list (optional)
                html = render_to_string("orders/order_list.html", {"order": order, "request": request})
                order_url = reverse("orders:detail", args=[order.pk])

                created_orders.append({
                    "order_number": order.number,
                    "order_id": order.pk,
                    "order_url": order_url,
                    "html": html,
                    "order_total": str(total_value),  # stringify Decimal
                })

            # clear cart (store JSON-friendly primitives)
            request.session["cart"] = {"items": {}, "total_qty": 0, "total_amount": 0}
            request.session.modified = True

        return JsonResponse({"success": True, "orders": created_orders})

    except Exception as exc:
        import traceback, sys
        traceback.print_exc(file=sys.stderr)
        return JsonResponse({"success": False, "error": str(exc)}, status=500)


from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

import json
import logging
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

@require_POST
@login_required
def update_status(request, pk):
    """
    Update order.status via POST.
    Accepts JSON body { "status": "CONFIRMED" } or form POST "status=CONFIRMED".
    Returns JSON { success: True } or { success: False, error: "..." } with proper status code.
    """
    order = get_object_or_404(Order, pk=pk)

    # parse incoming status (JSON preferred, fallback to POST form)
    new_status = None
    try:
        if request.content_type and "application/json" in request.content_type:
            payload = json.loads(request.body.decode("utf-8") or "{}")
            new_status = payload.get("status")
        else:
            # fallback for form-encoded posts
            new_status = request.POST.get("status") or request.GET.get("status")
    except Exception as exc:
        logger.exception("Failed to parse update_status payload for Order %s", pk)
        return JsonResponse({"success": False, "error": "Invalid request payload"}, status=400)

    if not new_status:
        return JsonResponse({"success": False, "error": "Missing 'status' value"}, status=400)

    # normalize
    new_status = str(new_status).strip()

    # Allow case-insensitive matching against your Order.Status choices keys
    valid_keys = {k: k for k, _ in Order.Status.choices}  # e.g. {'PENDING': 'PENDING', ...} or {'pending': 'pending'}
    # Normalize keys for matching (both uppercase and lowercase supported)
    valid_keys_ci = {k.upper(): k for k, _ in Order.Status.choices}
    # Try direct match first, then case-insensitive
    if new_status in valid_keys:
        chosen = new_status
    elif new_status.upper() in valid_keys_ci:
        chosen = valid_keys_ci[new_status.upper()]
    else:
        # provide helpful error listing allowed values
        allowed = [k for k, _ in Order.Status.choices]
        return JsonResponse({"success": False, "error": f"Invalid status. Allowed: {allowed}"}, status=400)

    # permission check: only allowed actors can change to certain statuses
    user_org = getattr(request.user, "organization", None)
    # Example rules: wholesaler can CONFIRM/SHIP, retailer can CANCEL, staff can do anything
    if not (request.user.is_staff or request.user.is_superuser):
        if chosen in ("CONFIRMED", "SHIPPED") and user_org != order.wholesaler:
            return JsonResponse({"success": False, "error": "Only wholesaler can confirm/ship this order"}, status=403)
        if chosen in ("CANCELLED",) and user_org != order.retailer:
            return JsonResponse({"success": False, "error": "Only retailer can cancel this order"}, status=403)

    # Optionally validate allowed transitions (example)
    allowed_transitions = {
        getattr(Order.Status, "PENDING", "PENDING"): {getattr(Order.Status, "CONFIRMED", "CONFIRMED"), getattr(Order.Status, "CANCELLED", "CANCELLED")},
        getattr(Order.Status, "CONFIRMED", "CONFIRMED"): {getattr(Order.Status, "SHIPPED", "SHIPPED")},
        getattr(Order.Status, "SHIPPED", "SHIPPED"): {getattr(Order.Status, "DELIVERED", "DELIVERED")},
    }
    current = order.status
    # allow staff to bypass transition checks
    if not (request.user.is_staff or request.user.is_superuser):
        allowed_next = allowed_transitions.get(current, None)
        if allowed_next is not None and chosen not in allowed_next:
            return JsonResponse({"success": False, "error": f"Invalid status transition from {current} to {chosen}"}, status=400)

    # perform update
    try:
        order.status = chosen
        order.save(update_fields=["status"])
        # optionally log/emit activity here
        return JsonResponse({"success": True, "status": chosen})
    except Exception as exc:
        logger.exception("Failed to update order %s status -> %s", pk, chosen)
        return JsonResponse({"success": False, "error": "Server error while updating status"}, status=500)



from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

# ... other imports ...

@require_POST
@login_required
def cancel_order(request, pk):
    """
    Allow retailer (owner) to cancel an order while it's in a cancellable state.
    Returns: redirect to order detail (or orders:list if not allowed).
    """
    order = get_object_or_404(Order, pk=pk)

    # Permission: staff or wholesaler or retailer? Here we allow retailer who placed it, or staff
    user_org = getattr(request.user, "organization", None)
    if not (request.user.is_staff or request.user.is_superuser or (user_org and user_org == order.retailer)):
        messages.error(request, "You do not have permission to cancel this order.")
        return redirect("orders:detail", pk=order.pk)

    # Allowed cancellation states — adjust to your model's choices
    allowed_cancel_states = {Order.Status.PENDING}
    # If your Order.Status includes CANCELLED, use that constant elsewhere
    try:
        current_status = order.status
    except Exception:
        current_status = None

    if current_status not in allowed_cancel_states and not request.user.is_staff:
        messages.error(request, "Order cannot be cancelled at this stage.")
        return redirect("orders:detail", pk=order.pk)

    # Perform cancellation
    order.status = getattr(Order.Status, "CANCELLED", "CANCELLED")  # set to constant if exists, otherwise string
    # Optionally update payment_status or other fields
    order.payment_status = getattr(order, "payment_status", "Cancelled") or "Cancelled"
    order.save(update_fields=["status", "payment_status"])

    messages.success(request, f"Order {order.number} has been cancelled.")
    return redirect("orders:detail", pk=order.pk)
