
from django.urls import path

from .views import (
    product_list,
    product_detail,
    cart_view,
    cart_update,
    cart_remove,
    checkout_view,
    order_confirmation,
)

urlpatterns = [
    # Product catalog / homepage
    path("", product_list, name="product_list"),

    # Shopping cart
    path("cart/", cart_view, name="cart"),
    path(
        "cart/update/<int:item_id>/",
        cart_update,
        name="cart_update",
    ),
    path(
        "cart/remove/<int:item_id>/",
        cart_remove,
        name="cart_remove",
    ),

    # Checkout
    path("checkout/", checkout_view, name="checkout"),

    # Order confirmation
    path(
        "orders/<int:order_id>/",
        order_confirmation,
        name="order_confirmation",
    ),

    # Product detail — keep this route last
    path(
        "<slug:slug>/",
        product_detail,
        name="product_detail",
    ),
]
