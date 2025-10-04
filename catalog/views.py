# catalog/views.py

import json
import csv
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import Sum, Count, F, FloatField, ExpressionWrapper, Prefetch, Avg, Value, DecimalField
from django.db.models.functions import TruncDay, Coalesce
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.http import require_POST

from accounts.models import Organization, CustomerProfile
from orders.models import Order, OrderItem
from .models import Product, Category, SizeStock, Size, ProductImage, CategorySize, MoqOption, Hero, TopBrand
from .forms import ProductForm


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def require_wholesaler(user) -> bool:
    return getattr(user, "role", None) == "wholesaler" and getattr(user, "organization", None)

# ---------------------------------------------------------------------
# Public/Retailer Views
# ---------------------------------------------------------------------
def product_list(request):
    qs = Product.objects.filter(is_active=True).annotate(
        total_quantity=Coalesce(Sum('size_stocks__quantity'), Value(0))
    ).filter(total_quantity__gt=0).select_related("owner", "category")

    wholesaler_id = request.GET.get("wholesaler")
    category_id = request.GET.get("category")
    sort = request.GET.get("sort", "newest")

    if wholesaler_id:
        try:
            qs = qs.filter(owner_id=int(wholesaler_id))
        except (TypeError, ValueError):
            pass

    if category_id:
        try:
            qs = qs.filter(category_id=int(category_id))
        except (TypeError, ValueError):
            pass

    sort_map = {
        "newest": "-id",
        "price_desc": "-wholesale_price",
        "price_asc": "wholesale_price",
    }
    qs = qs.order_by(sort_map.get(sort, "-id"))

    wholesalers = Organization.objects.filter(org_type="wholesaler").prefetch_related(
        Prefetch('users__profile', to_attr='user_profile')
    )[:20]

    context = {
        "products": qs,
        "wholesalers": wholesalers,
        "categories": Category.objects.all(),
    }
    return render(request, "catalog/product_list.html", context)

def product_detail(request, pk):
    product = get_object_or_404(Product.objects.select_related("category", "owner"), pk=pk, is_active=True)
    related = Product.objects.filter(category=product.category, is_active=True).exclude(pk=product.pk)[:4]
    return render(request, "catalog/product_detail.html", {"product": product, "related": related})

# ---------------------------------------------------------------------
# Wholesaler Views (CORRECTED)
# ---------------------------------------------------------------------
@login_required
@user_passes_test(require_wholesaler)
def wholesaler_dashboard(request):
    org = request.user.organization
    
    # Base queryset for all active products
    all_products_qs = Product.objects.filter(owner=org, is_active=True)

    # Annotate with total_stock to calculate in the DB. This is the fix.
    products_with_stock = all_products_qs.annotate(
        total_stock=Coalesce(Sum('size_stocks__quantity'), Value(0))
    ).order_by("name")

    # Handle filtering based on the annotated total_stock
    filter_param = request.GET.get("filter")
    if filter_param == "out":
        products_qs = products_with_stock.filter(total_stock=0)
    elif filter_param == "low":
        products_qs = products_with_stock.filter(total_stock__gt=0, total_stock__lte=5)
    else:
        products_qs = products_with_stock

    # Calculate stats efficiently from the annotated queryset
    total_products = all_products_qs.count()
    out_of_stock_count = products_with_stock.filter(total_stock=0).count()
    low_stock_count = products_with_stock.filter(total_stock__gt=0, total_stock__lte=5).count()

    context = {
        "products": products_qs,
        "total_products": total_products,
        "out_of_stock_count": out_of_stock_count,
        "low_stock_count": low_stock_count,
    }
    return render(request, "catalog/wholesaler_dashboard.html", context)



# ---------------------------------------------------------------------
# Product add/edit (Updated)
# ---------------------------------------------------------------------
@login_required
@user_passes_test(require_wholesaler)
def product_add(request):
    org = request.user.organization
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                product = form.save(commit=False)
                product.owner = org
                product.save()

                # Process and Save MOQ Options
                moq_data = {}
                for key, value in request.POST.items():
                    if key.startswith('moq-') and value and int(value) > 0:
                        parts = key.split('-')
                        index, size_name = parts[1], parts[3]
                        if index not in moq_data:
                            moq_data[index] = {}
                        moq_data[index][size_name] = int(value)
                for config in moq_data.values():
                    if any(v > 0 for v in config.values()):
                        MoqOption.objects.create(product=product, configuration=config)

                # Process and Save Stock by Size
                for key, value in request.POST.items():
                    if key.startswith("stock-size-") and value:
                        try:
                            if int(value) > 0:
                                size_id = int(key.split("-")[2])
                                SizeStock.objects.create(product=product, size_id=size_id, quantity=int(value))
                        except (ValueError, IndexError):
                            pass
                
                # Save images
                new_images = request.FILES.getlist("new_images")
                cover_choice = request.POST.get("cover_choice")

                saved_images = []
                for i, img in enumerate(new_images):
                    product_img = ProductImage.objects.create(product=product, image=img, position=i)
                    saved_images.append((f"new_{i}", product_img))

                # Set cover image
                if cover_choice:
                    if cover_choice.startswith("new_"):
                        idx = int(cover_choice.split("_")[1])
                        if 0 <= idx < len(saved_images):
                            product.image = saved_images[idx][1].image  # set cover from ProductImage
                            product.save()
                    elif cover_choice.isdigit():
                        try:
                            chosen_img = ProductImage.objects.get(id=int(cover_choice), product=product)
                            product.image = chosen_img.image
                            product.save()
                        except ProductImage.DoesNotExist:
                            pass
                else:
                    # Default: if no cover selected, use the first uploaded image
                    if saved_images:
                        product.image = saved_images[0][1].image
                        product.save()

            messages.success(request, "Product added successfully.")
            return redirect("catalog:wholesaler_dashboard")
    else:
        form = ProductForm()

    return render(request, "catalog/product_form.html", {
        "form": form,
        "mode": "add",
        "product": Product(),
        "existing_moqs_json": "[]",  # Pass an empty JSON array for new products
    })


@login_required
@user_passes_test(require_wholesaler)
def product_edit(request, pk):
    org = request.user.organization
    product = get_object_or_404(Product, pk=pk, owner=org)

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            with transaction.atomic():
                product = form.save()

                # Process and Save MOQ Options
                product.moq_options.all().delete()
                moq_data = {}
                for key, value in request.POST.items():
                    if key.startswith('moq-') and value:
                        parts = key.split('-')
                        index, size_name = parts[1], parts[3]
                        if index not in moq_data:
                            moq_data[index] = {}
                        moq_data[index][size_name] = int(value)
                for config in moq_data.values():
                    if any(v > 0 for v in config.values()):
                        MoqOption.objects.create(product=product, configuration=config)

                # Process and Save Stock by Size
                product.size_stocks.all().delete()
                for key, value in request.POST.items():
                    if key.startswith("stock-size-") and value:
                        try:
                            if int(value) > 0:
                                size_id = int(key.split("-")[2])
                                SizeStock.objects.create(product=product, size_id=size_id, quantity=int(value))
                        except (ValueError, IndexError):
                            pass

                # Update images
                new_images = request.FILES.getlist("new_images")
                cover_choice = request.POST.get("cover_choice")

                for i, img in enumerate(new_images):
                    ProductImage.objects.create(product=product, image=img, position=i)

                if cover_choice:
                    if cover_choice.startswith("new_"):
                        idx = int(cover_choice.split("_")[1])
                        if idx < len(new_images):
                            product.image = new_images[idx]
                            product.save()
                    elif cover_choice.isdigit():
                        try:
                            chosen_img = ProductImage.objects.get(id=int(cover_choice), product=product)
                            product.image = chosen_img.image
                            product.save()
                        except ProductImage.DoesNotExist:
                            pass

            messages.success(request, "Product updated successfully.")
            return redirect("catalog:wholesaler_dashboard")
    else:
        form = ProductForm(instance=product)
    
    # Prepare existing MOQ data as a JSON string for the template
    existing_moqs = list(product.moq_options.all().values_list('configuration', flat=True))
    
    return render(request, "catalog/product_form.html", {
        "form": form,
        "mode": "edit",
        "product": product,
        "existing_moqs_json": json.dumps(existing_moqs),  # Convert to JSON string
    })


@login_required
def product_image_delete(request, pk):
    if request.method != "POST":
        return HttpResponseForbidden("POST required")

    # Only allow deleting images that belong to the user's org
    img = get_object_or_404(
        ProductImage,
        pk=pk,
        product__owner=request.user.organization
    )

    # extra safety: don't allow deleting the current cover
    if img.product.image and img.image.name == img.product.image.name:
        return JsonResponse({"ok": False, "error": "Cannot delete cover image"}, status=400)

    img.delete()

    # AJAX path
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True})

    # Non-AJAX fallback
    return redirect("catalog:product_edit", pk=img.product_id)


# ---------------------------------------------------------------------
# Category sizes (AJAX)
# ---------------------------------------------------------------------
@login_required
def category_sizes(request, category_id):
    sizes = CategorySize.objects.filter(category_id=category_id).select_related("size")
    data = [{"id": cs.size.id, "name": cs.size.name} for cs in sizes]
    return JsonResponse(data, safe=False)


# ---------------------------------------------------------------------
# Delete product
# ---------------------------------------------------------------------
@login_required
@user_passes_test(require_wholesaler)
@require_POST
def delete_product(request, pk):
    org = request.user.organization
    product = get_object_or_404(Product, pk=pk, owner=org)

    # === UPDATE THE LOGIC HERE ===
    # Instead of deleting, we set it to inactive
    product.is_active = False
    product.save()
    
    messages.success(request, f"Product '{product.name}' has been archived and is no longer visible to retailers.")
    return redirect("catalog:wholesaler_dashboard")

# ==========================================================
#   REPORTS VIEW (CORRECTED)
# ==========================================================
@login_required
@user_passes_test(require_wholesaler)
def wholesale_reports(request):
    org = request.user.organization
    today = timezone.now().date()
    start_date = today - timedelta(days=29)

    orders_qs = Order.objects.filter(wholesaler=org, date__range=[start_date, today])
    delivered_orders = orders_qs.filter(status=Order.Status.DELIVERED)
    
    # === FIX IS HERE: Added output_field to Coalesce for Decimal fields ===
    key_metrics = delivered_orders.aggregate(
        total_sales=Coalesce(Sum('total_value'), Value(0), output_field=DecimalField()),
        total_items=Coalesce(Sum('items_count'), Value(0)),
        avg_order_value=Coalesce(Avg('total_value'), Value(0), output_field=DecimalField())
    )

    best_sellers = OrderItem.objects.filter(
        order__in=delivered_orders
    ).values(
        'product__name', 'product__sku'
    ).annotate(
        qty_sold=Sum('quantity'),
        revenue=Sum(F('quantity') * F('price'))
    ).order_by('-revenue')[:5]

    inventory_qs = Product.objects.filter(owner=org, is_active=True).annotate(
        total_stock=Coalesce(Sum('size_stocks__quantity'), Value(0))
    )
    
    inventory_snapshot = inventory_qs.aggregate(
        total_stock_units=Coalesce(Sum('total_stock'), Value(0))
    )
    low_stock_products = inventory_qs.filter(total_stock__gt=0, total_stock__lte=5)
    
    orders_by_status = orders_qs.values('status').annotate(count=Count('id')).order_by('-count')

    context = {
        "start_date": start_date,
        "end_date": today,
        "total_sales_value": key_metrics['total_sales'],
        "total_orders": orders_qs.count(),
        "total_items_sold": key_metrics['total_items'],
        "avg_order_value": key_metrics['avg_order_value'],
        "best_sellers": best_sellers,
        "total_stock": inventory_snapshot['total_stock_units'],
        "low_stock_products": low_stock_products,
        "orders_by_status": orders_by_status,
    }
    return render(request, "catalog/reports.html", context)


def reports_export_csv(request):
    """
    Simple CSV export of best_sellers and product stock for the wholesaler.
    """
    org = getattr(request.user, "organization", None)
    if org is None:
        return HttpResponse("No organization", status=400)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=reports.csv"

    writer = csv.writer(response)
    writer.writerow(["Product SKU", "Product Name", "Total Stock", "Qty Sold", "Revenue"])

    # join best sellers and current stock
    sellers = (
        OrderItem.objects.filter(product__owner=org)
        .values("product__id", "product__sku", "product__name")
        .annotate(qty_sold=Sum("quantity"), revenue=Sum(ExpressionWrapper(F("quantity") * F("price"), output_field=FloatField())))
        .order_by("-qty_sold")
    )

    # Build map of stock by product id
    products = Product.objects.filter(owner=org).prefetch_related("size_stocks")
    stock_map = {p.id: p.total_stock for p in products}

    for s in sellers:
        pid = s["product__id"]
        writer.writerow([
            s["product__sku"],
            s["product__name"],
            stock_map.get(pid, 0),
            s.get("qty_sold") or 0,
            s.get("revenue") or 0,
        ])

    return response


# ---------------------------------------------------------------------
# Home page
# ---------------------------------------------------------------------
def home(request):
    hero = Hero.objects.filter(is_active=True).order_by('order').first()
    if not hero:
        hero = Hero.objects.last()  # fallback

    top_brands = TopBrand.objects.filter(is_active=True).order_by('order')[:4]
    categories = Category.objects.all()
    wholesalers = Organization.objects.filter(org_type="wholesaler")

    return render(request, "catalog/home_public.html", {
        "hero": hero,
        "top_brands": top_brands,
        "categories": categories,
        "wholesalers": wholesalers,
    })