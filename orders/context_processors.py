def cart_count(request):
    cart = request.session.get("cart", {})
    return {"cart_count": len(cart.get("items", {})) if cart else 0}
