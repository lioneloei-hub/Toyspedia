from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .image_search import reset_index
from .models import Product


@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
def _product_changed(sender, **kwargs):
    # Changing a product (active flag, photo, embedding) can change the search results.
    reset_index()
