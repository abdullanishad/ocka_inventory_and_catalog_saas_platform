# orders/views.py

from __future__ import annotations

import csv
import json
import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Dict, Tuple

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import (Q, Sum, F, Value, DecimalField, IntegerField)
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from accounts.models import Organization
from catalog.models import Product, SizeStock, Size
from .cart import get_cart, add_item, update_quantity, remove_item
from .models import Order, OrderItem


# orders/views.py
# ... (add ShipmentForm to your imports)
from .forms import ShipmentForm
from .models import Order, OrderItem, Shipment # Make sure Shipment is imported

logger = logging.getLogger(__name__)

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

        # We only need to annotate the item count now.
        qs = qs.annotate(
            annot_items_count=Coalesce(Sum("items__quantity"), Value(0), output_field=IntegerField())
        )
        
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
        # --- THIS IS THE FIX ---
        if e:
            # To include all records on the end date, filter for less than the *next day*.
            qs = qs.filter(date__lt=e + timedelta(days=1))
        # --- END OF FIX ---
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        org = getattr(user, "organization", None)
        is_wholesaler = False
        if user.is_staff or user.is_superuser:
            is_wholesaler = False
        elif org and getattr(org, "org_type", None) == "wholesaler":
            is_wholesaler = True

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

        counts = {"all": base.count()}
        for status_value, _ in Order.Status.choices:
            counts[status_value] = base.filter(status=status_value).count()

        tabs = [("all", "All")] + list(Order.Status.choices)

        ctx.update({
            "counts": counts,
            "request_params": self.request.GET,
            "tabs": tabs,
            "active_status": self.request.GET.get("status", "all"),
            "is_wholesaler": is_wholesaler,
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
    writer.writerow(["Order #", "Date", "Retailer", "Retailer City", "Wholesaler", "Items", "Value", "Payment", "Payment Status", "Status"])
    for o in qs:
        writer.writerow([
            o.number, o.date.isoformat(),
            getattr(o.retailer, "name", ""), getattr(o.retailer, "city", ""),
            getattr(o.wholesaler, "name", ""),
            o.annot_items_count, f"{o.annot_total_value}",
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
    if not (request.user.is_staff or request.user.is_superuser or (org and (org == order.retailer or org == order.wholesaler))):
        messages.error(request, "You do not have access to this order.")
        return redirect("orders:list")

    placed_at = order.date or getattr(order, "created_at", None)

    try:
        raw_items_qs = order.items.select_related("product").all()
    except Exception:
        raw_items_qs = order.orderitem_set.select_related("product").all()

    order_items = []
    for oi in raw_items_qs:
        try:
            price = Decimal(str(oi.price))
        except (InvalidOperation, TypeError, ValueError):
            price = Decimal("0")
        qty = int(getattr(oi, "quantity", 1) or 0)
        subtotal = price * qty
        order_items.append({
            "obj": oi,
            "product": getattr(oi, "product", None),
            "quantity": qty,
            "price": price,
            "subtotal": subtotal,
        })

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
def view_cart(request):
    cart = get_cart(request)
    items = list(cart["items"].values())
    for it in items:
        it["price"] = f"{Decimal(str(it['price'])):.2f}"
    ctx = {
        "items": items,
        "total": cart["total_amount"],
    }
    return render(request, "orders/cart.html", ctx)

@require_POST
def add_to_cart(request):
    pid = request.POST.get("product_id")
    qty = request.POST.get("quantity")
    price = request.POST.get("price")
    moq_label = request.POST.get("moq_label")
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

    add_item(
        request,
        product=product,
        quantity=qty,
        price=price,
        moq_label=moq_label,
        image_url=image_url or (product.image.url if getattr(product, "image", None) else None)
    )

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
    remove_item(request, key)
    return redirect("orders:view_cart")

def checkout(request):
    cart = get_cart(request)
    return render(request, "orders/checkout.html", {"cart": cart})

# orders/views.py

# ... (imports and other views up to ajax_checkout)

@require_POST
@login_required
def ajax_checkout(request):
    try:
        cart = get_cart(request)
        raw_items = list(cart.get("items", {}).values())
        if not raw_items:
            return JsonResponse({"success": False, "error": "Cart is empty."}, status=400)

        retailer_org = getattr(request.user, "organization", None)
        if not retailer_org or getattr(retailer_org, "org_type", None) != "retailer":
            return JsonResponse({"success": False, "error": "Only retailers can place orders."}, status=403)

        wholesaler_map = {}
        prod_cache = {}

        for it in raw_items:
            pid = it.get("product_id")
            if not pid:
                return JsonResponse({"success": False, "error": "Cart item missing product id."}, status=400)
            
            if pid not in prod_cache:
                try:
                    prod_cache[pid] = Product.objects.select_related("owner").get(pk=pid)
                except Product.DoesNotExist:
                    return JsonResponse({"success": False, "error": f"Product {pid} not found."}, status=400)
            
            product = prod_cache[pid]
            wholesaler = product.owner
            key = wholesaler.pk if wholesaler else "__none__"
            
            wholesaler_map.setdefault(key, {"wholesaler": wholesaler, "items": []})
            
            qty = int(it.get("quantity", 1))
            price = Decimal(str(it.get("price", 0)))
            
            wholesaler_map[key]["items"].append({
                "product": product,
                "quantity": qty,
                "price": price,
                "moq_label": it.get("moq"),
            })

        created_orders = []
        
        with transaction.atomic():
            for entry in wholesaler_map.values():
                wholesaler = entry["wholesaler"]
                items = entry["items"]
                
                # Stock deduction logic
                for item_data in items:
                    product = item_data['product']
                    ordered_qty = item_data['quantity']
                    moq_label = item_data['moq_label']

                    if not moq_label:
                        continue

                    parts = moq_label.split(' | ')
                    if len(parts) != 3:
                        continue

                    pack_size_str = parts[0].split(' ')[0]
                    if not pack_size_str.isdigit():
                        continue
                    pack_size = int(pack_size_str)

                    size_names = [s.strip() for s in parts[1].split(',')]
                    ratio_nums = [int(r) for r in parts[2].split(':')]

                    if len(size_names) != len(ratio_nums) or pack_size == 0:
                        continue

                    num_packs = ordered_qty // pack_size
                    
                    size_name_to_id = {s.name: s.id for s in Size.objects.filter(name__in=size_names)}

                    for i, size_name in enumerate(size_names):
                        qty_to_deduct = num_packs * ratio_nums[i]
                        size_id = size_name_to_id.get(size_name)
                        
                        if not size_id or qty_to_deduct == 0:
                            continue

                        stock_record = SizeStock.objects.select_for_update().get(product=product, size_id=size_id)
                        
                        if stock_record.quantity < qty_to_deduct:
                            raise Exception(f"Not enough stock for {product.name} (Size: {size_name}).")
                        
                        SizeStock.objects.filter(pk=stock_record.pk).update(quantity=F('quantity') - qty_to_deduct)

                # --- UPDATED CODE LOGIC ---
                subtotal = sum(i["price"] * i["quantity"] for i in items)
                order_total_for_json = subtotal # Keep this for the JSON response

                order = Order.objects.create(
                    number=_new_order_number(),
                    retailer=retailer_org,
                    wholesaler=wholesaler,
                    subtotal=subtotal, # Use the new subtotal field
                    status=Order.Status.PENDING,
                )
                # --- END OF UPDATED CODE LOGIC ---

                # --- THIS IS THE FIX ---
                # We need to save the 'moq_label' to the 'pack_details' field
                for it in items:
                    OrderItem.objects.create(
                        order=order, 
                        product=it["product"], 
                        quantity=it["quantity"], 
                        price=it["price"],
                        pack_details=it.get("moq_label") # Add this line
                    )
                # --- END OF FIX ---
                
                created_orders.append({
                    "order_number": order.number,
                    "order_id": order.pk,
                    "order_url": reverse("orders:detail", args=[order.pk]),
                    "order_total": str(order_total_for_json),
                })

            # Clear cart
            request.session["cart"] = {"items": {}, "total_qty": 0, "total_amount": "0.00"}
            request.session.modified = True

        return JsonResponse({"success": True, "orders": created_orders})

    except Exception as exc:
        logger.exception("Error during checkout")
        return JsonResponse({"success": False, "error": str(exc)}, status=500)
    

@require_POST
@login_required
def update_status(request, pk):
    """
    Update order.status via POST with comprehensive validation and security checks.
    """
    order = get_object_or_404(Order, pk=pk)
    
    # Parse incoming status (using improved parsing from code 2)
    new_status = None
    try:
        if request.content_type and "application/json" in request.content_type:
            payload = json.loads(request.body.decode("utf-8") or "{}")
            new_status = payload.get("status")
        else:
            new_status = request.POST.get("status") or request.GET.get("status")
    except Exception as exc:
        logger.exception("Failed to parse update_status payload for Order %s", pk)
        return JsonResponse({"success": False, "error": "Invalid request payload"}, status=400)

    if not new_status:
        return JsonResponse({"success": False, "error": "Missing 'status' value"}, status=400)

    # Case-insensitive status matching (using improved matching from code 2)
    new_status = str(new_status).strip()
    valid_keys_ci = {k.upper(): k for k, _ in Order.Status.choices}
    
    if new_status.upper() in valid_keys_ci:
        chosen_status = valid_keys_ci[new_status.upper()]
    else:
        allowed = [k for k, _ in Order.Status.choices]
        return JsonResponse({"success": False, "error": f"Invalid status. Allowed: {allowed}"}, status=400)

    # === UPDATED TRANSITION RULES (from code 1) ===
    allowed_transitions = {
        Order.Status.PENDING: {Order.Status.AWAITING_PAYMENT, Order.Status.REJECTED},
        Order.Status.AWAITING_PAYMENT: {Order.Status.PAID, Order.Status.CANCELLED},
        Order.Status.PAID: {Order.Status.SHIPPED},
        Order.Status.SHIPPED: {Order.Status.DELIVERED, Order.Status.COMPLETED},
        Order.Status.DELIVERED: {Order.Status.COMPLETED},
    }
    
    current_status = order.status
    user = request.user
    user_org = getattr(user, "organization", None)

    # Staff can bypass transition rules
    if not (user.is_staff or user.is_superuser):
        # Check if the transition is allowed
        allowed_next_statuses = allowed_transitions.get(current_status, set())
        if chosen_status not in allowed_next_statuses:
            return JsonResponse({"success": False, "error": f"Invalid status transition from {current_status} to {chosen_status}"}, status=400)

        # Check permissions (enhanced permission logic from code 1)
        if chosen_status in (Order.Status.AWAITING_PAYMENT, Order.Status.REJECTED, Order.Status.SHIPPED) and user_org != order.wholesaler:
            return JsonResponse({"success": False, "error": "Only the wholesaler can perform this action."}, status=403)
        if chosen_status == Order.Status.CANCELLED and user_org != order.retailer:
            return JsonResponse({"success": False, "error": "Only the retailer can perform this action."}, status=403)

    # Perform update
    try:
        order.status = chosen_status
        order.save(update_fields=["status"])
        # Add success message as in code 1
        messages.success(request, f"Order status updated to {order.get_status_display()}.")
        return redirect('orders:detail', pk=order.pk)
    except Exception as exc:
        logger.exception("Failed to update order %s status -> %s", pk, chosen_status)
        return JsonResponse({"success": False, "error": "Server error while updating status."}, status=500)
    
@require_POST
@login_required
def cancel_order(request, pk):
    """
    Allow retailer (owner) to cancel an order while it's in a cancellable state.
    """
    order = get_object_or_404(Order, pk=pk)
    user_org = getattr(request.user, "organization", None)
    
    if not (request.user.is_staff or request.user.is_superuser or (user_org and user_org == order.retailer)):
        messages.error(request, "You do not have permission to cancel this order.")
        return redirect("orders:detail", pk=order.pk)

    # Allowed cancellation states
    allowed_cancel_states = {Order.Status.PENDING}
    current_status = order.status

    if current_status not in allowed_cancel_states and not request.user.is_staff:
        messages.error(request, "Order cannot be cancelled at this stage.")
        return redirect("orders:detail", pk=order.pk)

    # Perform cancellation
    order.status = getattr(Order.Status, "CANCELLED", "CANCELLED")
    order.payment_status = getattr(order, "payment_status", "Cancelled") or "Cancelled"
    order.save(update_fields=["status", "payment_status"])

    messages.success(request, f"Order {order.number} has been cancelled.")
    return redirect("orders:detail", pk=order.pk)


# orders/views.py
import razorpay
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

# Initialize Razorpay client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

# orders/views.py
@login_required
def start_payment(request, pk):
    order = get_object_or_404(Order, pk=pk)
    
    # Create a Razorpay Order
    razorpay_order = client.order.create({
        "amount": int(order.grand_total * 100), # Use grand_total
        "currency": "INR",
        "receipt": order.number,
    })
    
    order.razorpay_order_id = razorpay_order['id']
    order.save()
    
    context = {
        'order': order,
        'razorpay_order_id': razorpay_order['id'],
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'amount': int(order.grand_total * 100), # Use grand_total
    }
    return render(request, 'orders/payment.html', context)

@csrf_exempt
def payment_success(request):
    if request.method == "POST":
        payload = request.POST
        razorpay_order_id = payload.get('razorpay_order_id')
        razorpay_payment_id = payload.get('razorpay_payment_id')
        razorpay_signature = payload.get('razorpay_signature')

        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }

        try:
            # Verify the payment signature
            client.utility.verify_payment_signature(params_dict)
            
            # Find the order and update its status
            order = Order.objects.get(razorpay_order_id=razorpay_order_id)
            order.razorpay_payment_id = razorpay_payment_id
            order.razorpay_signature = razorpay_signature
            order.status = Order.Status.PAID # Payment is now held in Escrow
            order.payment_status = "Paid" # Also update the text status

            # --- NEW LOGIC TO FETCH PAYMENT METHOD ---
            try:
                payment_details = client.payment.fetch(razorpay_payment_id)
                method = payment_details.get('method')
                # Check if the fetched method is a valid choice in our model
                if method in [choice[0] for choice in Order.PaymentMethod.choices]:
                    order.payment_method = method
            except Exception as e:
                logger.error(f"Could not fetch payment method for {razorpay_payment_id}: {e}")
            # --- END OF NEW LOGIC ---

            order.save()
            
            return render(request, 'orders/payment_success.html', {'order': order})
        except Exception as e:
            # Signature verification failed
            return render(request, 'orders/payment_failed.html')
        




# ... (rest of your views)

@login_required
def add_shipment(request, pk):
    order = get_object_or_404(Order, pk=pk)
    
    # Security check: only the wholesaler of this order can add shipment info
    if request.user.organization != order.wholesaler:
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('orders:detail', pk=order.pk)

    if request.method == 'POST':
        form = ShipmentForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                shipment = form.save(commit=False)
                shipment.order = order
                shipment.save()

                # Update the order status to SHIPPED
                order.status = Order.Status.SHIPPED
                order.save()

            messages.success(request, f"Shipping information added for order {order.number}.")
            return redirect('orders:detail', pk=order.pk)
    else:
        form = ShipmentForm()

    return render(request, 'orders/shipment_form.html', {'form': form, 'order': order})

# orders/views.py
# ... (imports)

@login_required
def add_shipping_and_gst(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.user.organization != order.wholesaler:
        messages.error(request, "Permission denied.")
        return redirect('orders:detail', pk=pk)

    if request.method == 'POST':
        shipping_charge_str = request.POST.get('shipping_charge', '0')
        # --- ADD THIS LINE ---
        gst_amount_str = request.POST.get('gst_amount', '0')
        
        try:
            order.shipping_charge = Decimal(shipping_charge_str)
            # --- CHANGE IS HERE ---
            order.gst_amount = Decimal(gst_amount_str)
            
            # Recalculate the grand total with the new manual values
            order.grand_total = order.subtotal + order.shipping_charge + order.gst_amount
            
            # Update status and save
            order.status = Order.Status.AWAITING_PAYMENT
            order.save()
            
            messages.success(request, "Shipping & GST added and order confirmed. The retailer has been notified to pay.")
            return redirect('orders:detail', pk=pk)
        except Exception:
            messages.error(request, "Invalid shipping charge or GST amount.")

    return render(request, 'orders/add_shipping_form.html', {'order': order})