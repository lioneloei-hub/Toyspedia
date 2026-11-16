from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings 
from django.conf.urls.static import static
from store.views import home

urlpatterns = [
    # path("", RedirectView.as_view(pattern_name="product_list", permanent=False)),
    path("", home, name="home"),
    path('admin/', admin.site.urls),
    path("products/", include("store.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)