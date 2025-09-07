import json
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction

from accounts.models import Organization
from orders.models import Order, OrderItem
from .models import Product, Category, SizeStock, Size, ProductImage, CategorySize
from .forms import ProductForm


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def require_wholesaler(user) -> bool:
    """
    Returns True only if the user is a wholesaler
    and linked to an organization.
    """
    return getattr(user, "role", None) == "wholesaler" and getattr(user, "organization", None)


# ---------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------
def home(request):
    wholesalers = Organization.objects.filter(org_type="wholesaler")
    categories = Category.objects.all()

    return render(request, "catalog/home_public.html", {
        "wholesalers": wholesalers,
        "categories": categories,
    })



def product_list(request):
    qs = Product.objects.select_related("owner", "category")

    wholesaler_id = request.GET.get("wholesaler")
    category_id = request.GET.get("category")
    sort = request.GET.get("sort", "newest")

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

    sort_map = {
        "newest": "-id",
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



# ---------------------------------------------------------------------
# Wholesaler dashboard
# ---------------------------------------------------------------------
@login_required
@user_passes_test(require_wholesaler)
def wholesaler_dashboard(request):
    org = request.user.organization
    qs = Product.objects.filter(owner=org).order_by("name")

    total_products = qs.count()
    out_of_stock = sum(1 for p in qs if p.total_stock == 0)
    low_stock = sum(1 for p in qs if 0 < p.total_stock <= 5)

    filter_param = request.GET.get("filter")
    if filter_param == "out":
        qs = [p for p in qs if p.total_stock == 0]
    elif filter_param == "low":
        qs = [p for p in qs if 0 < p.total_stock <= 5]

    context = {
        "products": qs,
        "total_products": total_products,
        "out_of_stock": out_of_stock,
        "low_stock": low_stock,
    }
    return render(request, "catalog/wholesaler_dashboard.html", context)


# ---------------------------------------------------------------------
# Product add/edit
# ---------------------------------------------------------------------
@login_required
@user_passes_test(require_wholesaler)
def product_add(request):
    org = request.user.organization
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.owner = org
            product.save()

            # --- Save stock by size ---
            for key, value in request.POST.items():
                if key.startswith("size_") and value:
                    try:
                        qty = int(value)
                        if qty > 0:
                            size_id = int(key.split("_")[1])
                            if Size.objects.filter(id=size_id).exists():
                                SizeStock.objects.create(product=product, size_id=size_id, quantity=qty)
                    except ValueError:
                        pass

            # --- Save images ---
            new_images = request.FILES.getlist("new_images")
            cover_choice = request.POST.get("cover_choice")

            saved_images = []
            for i, img in enumerate(new_images):
                product_img = ProductImage.objects.create(product=product, image=img, position=i)
                saved_images.append((f"new_{i}", product_img))

            # --- Set cover image ---
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
    })



@login_required
@user_passes_test(require_wholesaler)
def product_edit(request, pk):
    org = request.user.organization
    product = get_object_or_404(Product, pk=pk, owner=org)

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save()

            # --- Update size stock ---
            product.size_stocks.all().delete()
            for key, value in request.POST.items():
                if key.startswith("size_") and value:
                    try:
                        qty = int(value)
                        if qty > 0:
                            size_id = int(key.split("_")[1])
                            if Size.objects.filter(id=size_id).exists():
                                SizeStock.objects.create(product=product, size_id=size_id, quantity=qty)
                    except ValueError:
                        pass

            # --- Update images ---
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

    return render(request, "catalog/product_form.html", {
        "form": form,
        "mode": "edit",
        "product": product,
    })


# catalog/views.py
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from .models import ProductImage

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
def delete_product(request, pk):
    org = request.user.organization
    product = get_object_or_404(Product, pk=pk, owner=org)
    product.delete()
    return redirect("catalog:wholesaler_dashboard")
