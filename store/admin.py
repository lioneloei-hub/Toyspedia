from django.contrib import admin
from .models import Category, Product

# Register your models here.
admin.site.register(Category)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock", "is_active", "image_search_ready")
    list_filter = ("category",)
    search_fields = ("name",)

    @admin.display(boolean=True, description="Photo search ready")
    def image_search_ready(self, obj):
        # True once `python manage.py build_embeddings` has saved this product's fingerprint.
        return obj.embedding is not None
