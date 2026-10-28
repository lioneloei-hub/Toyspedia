from django.contrib import admin
from .models import Category, Product

# Register your models here.
admin.site.register(Category)
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
  list_display = ("name", "category", "price", "stock", "is_active")
  list_filter = ("category",)
  search_fields = ("name",)
  