
from django.urls import path

from .api import api_chat, api_search
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

    # JSON API for the chatbot and the photo search
    path("api/chat/", api_chat, name="api_chat"),
    path("api/search/", api_search, name="api_search"),

    # Product detail — keep this route last
    path(
        "<slug:slug>/",
        product_detail,
        name="product_detail",
    ),
]
