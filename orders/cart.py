# orders/cart.py
from decimal import Decimal

CART_KEY = "cart"

def _ensure(session):
    cart = session.get(CART_KEY)
    if not cart:
        cart = {"items": {}, "total_qty": 0, "total_amount": "0.00"}
        session[CART_KEY] = cart
    return cart

def _recalc(cart):
    total_qty = 0
    total_amount = Decimal("0.00")
    for it in cart["items"].values():
        total_qty += it["quantity"]
        total_amount += Decimal(str(it["price"])) * it["quantity"]
        it["subtotal"] = f"{(Decimal(str(it['price'])) * it['quantity']):.2f}"
    cart["total_qty"] = total_qty
    cart["total_amount"] = f"{total_amount:.2f}"

def get_cart(request):
    return _ensure(request.session)

def save(request, cart):
    _recalc(cart)
    request.session.modified = True

def item_key(product_id, moq_label=None):
    # So the same product with different MOQ selections are separate lines
    return f"{product_id}::{moq_label or ''}"

def add_item(request, *, product, quantity, price, moq_label=None, image_url=None):
    cart = get_cart(request)
    key = item_key(product.id, moq_label)
    items = cart["items"]

    if key in items:
        items[key]["quantity"] += quantity
    else:
        items[key] = {
            "key": key,
            "product_id": product.id,
            "name": product.name,
            "sku": str(getattr(product, "sku", "")),   # ✅ force to string
            "price": float(price),
            "quantity": int(quantity),
            "image": image_url,
            "moq": moq_label,  # e.g., "3 pcs | S,M,L | 1:1:1"
            "subtotal": "0.00",
        }
    save(request, cart)
    return cart

def update_quantity(request, key, quantity):
    cart = get_cart(request)
    if key in cart["items"]:
        if quantity <= 0:
            del cart["items"][key]
        else:
            cart["items"][key]["quantity"] = int(quantity)
        save(request, cart)
    return cart

def remove_item(request, key):
    cart = get_cart(request)
    if key in cart["items"]:
        del cart["items"][key]
        save(request, cart)
    return cart
