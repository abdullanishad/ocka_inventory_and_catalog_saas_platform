import json
from django.db import models
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required, user_passes_test

from .models import Product, Category  # remove StockTransaction
from orders.models import Order, OrderItem
from accounts.models import Organization


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def is_ajax(request) -> bool:
    return request.headers.get("x-requested-with") == "XMLHttpRequest"

def require_wholesaler(user) -> bool:
    """
    Used by user_passes_test – returns True only if the user is a wholesaler
    and linked to an organization.
    """
    return getattr(user, "role", None) == "wholesaler" and getattr(user, "organization", None)


# ---------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------
def home(request):
    return render(request, "home.html")

# catalog/views.py
from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from .models import Product, Category
from accounts.models import Organization

from django.shortcuts import render
from accounts.models import Organization
from .models import Product, Category

def product_list(request):
    qs = Product.objects.select_related("owner", "category")

    wholesaler_id = request.GET.get("wholesaler")
    category_id   = request.GET.get("category")
    sort          = request.GET.get("sort", "newest")

    if wholesaler_id:
        try:
            qs = qs.filter(owner_id=int(wholesaler_id), owner__org_type="wholesaler")
        except (TypeError, ValueError):
            pass

    if category_id:
        try:
            qs = qs.filter(category_id=int(category_id))
        except (TypeError, ValueError):
            pass

    # ✅ only 3 options now
    sort_map = {
        "newest": "-id",  # newest first by creation order
        "price_desc": "-wholesale_price",
        "price_asc": "wholesale_price",
    }
    qs = qs.order_by(sort_map.get(sort, "-id"))

    context = {
        "products": qs,
        "wholesalers": Organization.objects.filter(org_type="wholesaler")[:20],
        "categories": Category.objects.all(),
    }
    return render(request, "catalog/product_list.html", context)




def product_detail(request, pk):
    product = get_object_or_404(Product.objects.select_related("category", "owner"), pk=pk)
    related = Product.objects.filter(category=product.category).exclude(pk=product.pk)[:4]
    return render(request, "catalog/product_detail.html", {"product": product, "related": related})


def related_products(request, pk):
    product = get_object_or_404(Product, pk=pk)
    related = Product.objects.filter(category=product.category).exclude(pk=product.pk)[:4]
    data = [{
        "id": p.id,
        "name": p.name,
        "sku": p.sku,
        "wholesale_price": str(p.wholesale_price),
        "image": p.image.url if p.image else "",
    } for p in related]
    return JsonResponse({"related_products": data})


# ---------------------------------------------------------------------
# Retailer landing (simple showcase style)
# ---------------------------------------------------------------------
def retailer_dashboard(request):
    categories = Category.objects.all()
    wholesalers = Organization.objects.filter(org_type="wholesaler")[:3]
    for w in wholesalers:
        w.initials = "".join([part[0].upper() for part in w.name.split()[:2]]) or "W"
        w.distance = 5  # placeholder until you wire real geo
    return render(request, "catalog/retailer_dashboard.html", {
        "categories": categories,
        "wholesalers": wholesalers,
    })


# ---------------------------------------------------------------------
# Wholesaler dashboard (Products tab)
# ---------------------------------------------------------------------
# catalog/views.py
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.forms import modelformset_factory, Textarea
from django.shortcuts import render, redirect
from django.db import transaction

from .models import Product

# catalog/views.py
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.forms import modelformset_factory, Textarea
from django.shortcuts import render, redirect
from django.db import transaction

from .models import Product


@login_required
def wholesaler_dashboard(request):
    org = getattr(request.user, "organization", None)
    if not org or org.org_type != "wholesaler":
        messages.error(request, "Only wholesalers can access this dashboard.")
        return redirect("catalog:product_list")

    # how many blank rows to allow for quick add
    extra_rows = 2

    ProductFormSet = modelformset_factory(
        Product,
        fields=[
            "image",
            "name",
            "sku",
            "description",
            "wholesale_price",
            "current_stock",
        ],
        widgets={"description": Textarea(attrs={"rows": 2})},
        can_delete=True,
        extra=extra_rows,
    )

    qs = Product.objects.filter(owner=org).order_by("name")

    if request.method == "POST":
        formset = ProductFormSet(request.POST, request.FILES, queryset=qs)
        if formset.is_valid():
            from decimal import Decimal
            try:
                with transaction.atomic():
                    # delete rows ticked for removal
                    for f in formset.deleted_forms:
                        if f.instance.pk:
                            f.instance.delete()

                    # save new/edited rows safely
                    for f in formset.forms:
                        if f in formset.deleted_forms:
                            continue
                        if not f.has_changed():
                            continue

                        cd = getattr(f, "cleaned_data", {}) or {}
                        # skip completely empty extra rows
                        minimal_filled = any(
                            cd.get(x) not in (None, "", [])
                            for x in (
                                "name", "sku", "wholesale_price", "retail_price",
                                "current_stock", "description", "image"
                            )
                        )
                        if f.instance.pk is None and not minimal_filled:
                            continue

                        obj = f.save(commit=False)

                        # attach owner for new products
                        if obj.pk is None:
                            obj.owner = org

                        # safety defaults if fields are nullable in DB
                        if getattr(obj, "retail_price", None) is None:
                            # fall back to wholesale price or 0
                            obj.retail_price = getattr(obj, "wholesale_price", None) or Decimal("0.00")

                        # business rules (server-side guardrails)
                        if obj.wholesale_price is not None and obj.wholesale_price < Decimal("10"):
                            messages.error(request, f"{obj.name or 'Product'}: Wholesale rate must be ≥ 10.")
                            raise ValueError("Wholesale < 10")
                        # if obj.minimum_order_qty is not None and obj.minimum_order_qty < 1:
                        #     messages.error(request, f"{obj.name or 'Product'}: MOQ must be ≥ 1.")
                            raise ValueError("MOQ < 1")
                        if obj.current_stock is not None and obj.current_stock < 0:
                            obj.current_stock = 0  # normalize negatives

                        obj.save()

                    formset.save_m2m()  # harmless if no m2m

                messages.success(request, "Products saved successfully.")
                return redirect("catalog:wholesaler_dashboard")

            except Exception:
                # fall through to render the page with errors/messages
                pass
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        formset = ProductFormSet(queryset=qs)

    # ⬇️ Always return a response here
    context = {
        "product_formset": formset,
        # keep other context parts from your dashboard if you have them
    }
    return render(request, "catalog/wholesaler_dashboard.html", context)




# ---------------------------------------------------------------------
# Product create / update (one view handles both)
# ---------------------------------------------------------------------
from .forms import ProductForm

# catalog/views.py (add these)
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from .forms import ProductForm, SizeStockFormSet
from .models import Product

@login_required
def product_edit(request, pk=None):
    """Create or edit a product with per-size inventory."""
    org = getattr(request.user, "organization", None)
    if not org or org.org_type != "wholesaler":
        messages.error(request, "Only wholesalers can edit products.")
        return redirect("catalog:product_list")

    product = get_object_or_404(Product, pk=pk, owner=org) if pk else Product(owner=org)

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        formset = SizeStockFormSet(request.POST, instance=product)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                prod = form.save()
                formset.instance = prod
                formset.save()

                # Ensure at least one SizeStock (Stock ≥1 overall)
                if prod.size_stocks.count() == 0:
                    messages.error(request, "Add at least one size with quantity ≥ 1.")
                    raise transaction.TransactionManagementError

            messages.success(request, "Product saved.")
            return redirect("catalog:wholesaler_dashboard")
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = ProductForm(instance=product)
        formset = SizeStockFormSet(instance=product)

    return render(request, "catalog/product_edit.html", {
        "form": form, "formset": formset, "product": product,
    })



@login_required
@user_passes_test(require_wholesaler)
def delete_product(request, pk):
    org = request.user.organization
    product = get_object_or_404(Product, pk=pk, owner=org)
    product.delete()
    return redirect("catalog:wholesaler_dashboard")


# ---------------------------------------------------------------------
# Stock adjustments (API-style)
# ---------------------------------------------------------------------
@csrf_exempt
@login_required
@user_passes_test(require_wholesaler)
def adjust_stock(request, product_id):
    """
    POST JSON:
    {
      "transaction_type": "IN" | "OUT",
      "quantity": 20
    }
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    org = request.user.organization
    product = get_object_or_404(Product, id=product_id, owner=org)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    tx_type = data.get("transaction_type")
    qty = int(data.get("quantity", 0))

    if tx_type not in {"IN", "OUT"} or qty <= 0:
        return JsonResponse({"error": "Invalid payload"}, status=400)

    if tx_type == "OUT" and product.current_stock < qty:
        return JsonResponse({"error": f"Not enough stock. Available: {product.current_stock}"}, status=400)

    # apply
    product.current_stock = product.current_stock + qty if tx_type == "IN" else product.current_stock - qty
    product.save()

    StockTransaction.objects.create(
        product=product,
        transaction_type=tx_type,
        quantity=qty,
        created_by=request.user,
    )

    return JsonResponse({"message": f"Stock {tx_type} applied", "new_stock": product.current_stock})


# ---------------------------------------------------------------------
# Orders (API-style)
# ---------------------------------------------------------------------
@csrf_exempt
@login_required
def create_order(request):
    """
    POST JSON:
    {
      "seller_id": 1,
      "buyer_id": 2,
      "items": [{"product_id": 5, "quantity": 10, "price": 250.00}, ...]
    }
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    seller = get_object_or_404(Organization, id=data.get("seller_id"), org_type="wholesaler")
    buyer = get_object_or_404(Organization, id=data.get("buyer_id"), org_type="retailer")
    order = Order.objects.create(seller=seller, buyer=buyer, created_by=request.user)

    for item in data.get("items", []):
        product = get_object_or_404(Product, id=item.get("product_id"), owner=seller)
        qty = int(item.get("quantity", 0))
        price = item.get("price")

        if qty <= 0:
            return JsonResponse({"error": "Quantity must be > 0"}, status=400)

        if product.current_stock < qty:
            return JsonResponse({"error": f"Not enough stock for {product.name}. Available: {product.current_stock}"},
                                status=400)

        # reduce stock + record transaction
        product.current_stock -= qty
        product.save()
        StockTransaction.objects.create(product=product, transaction_type="OUT", quantity=qty, created_by=request.user)

        OrderItem.objects.create(order=order, product=product, quantity=qty, price=price)

    return JsonResponse({"message": "Order created", "order_id": order.id})


from django.shortcuts import render
from .models import Product, Category
from accounts.models import Organization

def user_has_wholesaler(user):
    if not user.is_authenticated:
        return False
    try:
        return Organization.objects.filter(user=user, org_type="wholesaler").exists()
    except Exception:
        # if your Organization model relates differently, adjust the filter
        return False

def home_ocka(request):
    wholesalers = Organization.objects.filter(org_type="wholesaler")[:8]
    categories  = Category.objects.all()[:8]
    featured_products = Product.objects.select_related("owner", "category").order_by("-id")[:8]

    # Decide where the Sell button should go
    if user_has_wholesaler(request.user):
        # adjust to your real url name if different
        sell_href = "catalog:wholesaler_dashboard"
    else:
        sell_href = "accounts:signup"

    return render(request, "catalog/home_public.html", {
        "wholesalers": wholesalers,
        "categories": categories,
        "featured_products": featured_products,
        "is_home": True,                 # tell the header we’re on the home page
        "sell_href_urlname": sell_href,  # pass the urlname so the template can {% url ... %}
        "request_params": request.GET,
    })


# catalog/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.forms import modelformset_factory
from .models import Product

# catalog/views.py
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.forms import modelformset_factory, Textarea
from django.shortcuts import render, redirect
from django.db import transaction

from .models import Product

@login_required
def bulk_update_products(request):
    # Only wholesalers can bulk update
    org = getattr(request.user, "organization", None)
    if not org or org.org_type != "wholesaler":
        messages.error(request, "Only wholesalers can bulk update products.")
        return redirect("catalog:product_list")

    # How many blank rows to display for new products
    try:
        extra_rows = max(0, min(50, int(request.GET.get("extra", 5))))
    except ValueError:
        extra_rows = 5

    ProductFormSet = modelformset_factory(
        Product,
        fields=[
            "name",
            "description",
            "image",
            "wholesale_price",
            "retail_price",
            "current_stock",
        ],
        widgets={"description": Textarea(attrs={"rows": 2, "class": "w-full border rounded px-2 py-1"})},
        can_delete=True,
        extra=extra_rows,            # 👈 show blank rows for new items
    )

    qs = Product.objects.filter(owner=org).order_by("name")

    if request.method == "POST":
        formset = ProductFormSet(request.POST, request.FILES, queryset=qs)
        if formset.is_valid():
            with transaction.atomic():
                # Save edited + new forms
                instances = formset.save(commit=False)

                # mark deleted objects
                for obj in formset.deleted_objects:
                    obj.delete()

                for obj in instances:
                    # if it's a newly created row, attach owner
                    if obj.pk is None:
                        obj.owner = org
                    obj.save()

            messages.success(request, "Products saved successfully.")
            return redirect("catalog:bulk_update_products")
        else:
            messages.error(request, "Please fix errors below.")
    else:
        formset = ProductFormSet(queryset=qs)

    return render(request, "catalog/bulk_update_products.html", {"formset": formset})
