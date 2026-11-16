
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .models import (
    Category,
    Product,
    Cart,
    CartItem,
    Order,
    OrderItem,
)

def home(request):
    products = Product.objects.filter(
        is_active=True
    ).order_by("-created_at")[:4]

    categories = Category.objects.all()[:4]

    return render(
        request,
        "store/home.html",
        {
            "products": products,
            "categories": categories,
        }
    )


def product_list(request):
    products = Product.objects.filter(is_active=True)

    category_slug = request.GET.get("category")
    if category_slug:
        products = products.filter(category__slug=category_slug)

    categories = Category.objects.all()

    # 24 products per page, so a big catalogue doesn't load all at once.
    page = Paginator(products.select_related("category").order_by("id"), 24).get_page(
        request.GET.get("page")
    )

    return render(
        request,
        "store/catalog.html",
        {
            "products": page,
            "page_obj": page,
            "categories": categories,
            "category_slug": category_slug or "",
        },
    )


@login_required
def product_detail(request, slug):
    product = get_object_or_404(
        Product,
        slug=slug,
        is_active=True,
    )

    if request.method == "POST":
        if product.stock <= 0:
            messages.error(request, "This product is out of stock.")
            return redirect("product_detail", slug=product.slug)

        cart, _ = Cart.objects.get_or_create(user=request.user)

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={"quantity": 1},
        )

        if not created:
            if cart_item.quantity >= product.stock:
                messages.error(
                    request,
                    "You have reached the maximum available stock.",
                )
                return redirect("product_detail", slug=product.slug)

            cart_item.quantity += 1
            cart_item.save(update_fields=["quantity"])

        messages.success(request, "Product added to your cart.")
        return redirect("cart")

    return render(
        request,
        "store/product_detail.html",
        {"product": product},
    )


@login_required
def cart_view(request):
    cart, created = Cart.objects.get_or_create(
        user=request.user
    )

    items = cart.items.select_related("product").all()

    total = sum(
        (item.subtotal for item in items),
        start=0,
    )

    return render(
        request,
        "store/cart.html",
        {
            "cart": cart,
            "items": items,
            "total": total,
        },
    )



@login_required
def cart_update(request, item_id):
    if request.method != "POST":
        return redirect("cart")

    cart_item = get_object_or_404(
        CartItem,
        pk=item_id,
        cart__user=request.user,
    )

    action = request.POST.get("action")

    if action == "increase":
        if cart_item.quantity < cart_item.product.stock:
            cart_item.quantity += 1
            cart_item.save(update_fields=["quantity"])
        else:
            messages.error(request, "Maximum available stock reached.")

    elif action == "decrease":
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save(update_fields=["quantity"])

    return redirect("cart")


@login_required
def cart_remove(request, item_id):
    if request.method != "POST":
        return redirect("cart")

    cart_item = get_object_or_404(
        CartItem,
        pk=item_id,
        cart__user=request.user,
    )

    cart_item.delete()
    messages.success(request, "Product removed from your cart.")

    return redirect("cart")


@login_required
def checkout_view(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)

    if request.method == "POST":
        try:
            with transaction.atomic():
                # Lock the cart rows and retrieve the current items.
                cart_items = list(
                    CartItem.objects.filter(cart=cart)
                    .select_related("product")
                )

                if not cart_items:
                    messages.error(request, "Your cart is empty.")
                    return redirect("cart")

                products = {}

                # Lock products and validate their current stock.
                for item in cart_items:
                    product = Product.objects.select_for_update().get(
                        pk=item.product_id
                    )
                    products[product.pk] = product

                    if not product.is_active:
                        raise ValueError(
                            f"{product.name} is no longer available."
                        )

                    if (
                        item.quantity <= 0
                        or item.quantity > product.stock
                    ):
                        raise ValueError(
                            f"Insufficient stock for {product.name}."
                        )

                total = sum(
                    products[item.product_id].price * item.quantity
                    for item in cart_items
                )

                order = Order.objects.create(
                    user=request.user,
                    total=total,
                    status="PENDING",
                )

                for item in cart_items:
                    product = products[item.product_id]

                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=item.quantity,
                        price=product.price,
                    )

                    product.stock -= item.quantity
                    product.save(update_fields=["stock"])

                CartItem.objects.filter(cart=cart).delete()

            # Redirect after POST to avoid resubmitting the order on refresh.
            return redirect("order_confirmation", order_id=order.pk)

        except ValueError as error:
            messages.error(request, str(error))
            return redirect("cart")

    items = list(
        cart.items.select_related("product").all()
    )

    if not items:
        messages.info(request, "Your cart is empty.")
        return redirect("cart")

    total = sum(
        item.product.price * item.quantity
        for item in items
    )

    return render(
        request,
        "store/checkout.html",
        {
            "cart": cart,
            "items": items,
            "total": total,
        },
    )


@login_required
def order_confirmation(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        pk=order_id,
        user=request.user,
    )

    return render(
        request,
        "store/order_confirmation.html",
        {"order": order},
    )
