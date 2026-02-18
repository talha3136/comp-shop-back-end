"""
URL configuration for Mobile Shop Management System.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from drf_yasg import openapi
from accounts.views import index

# Swagger schema view
sw='swagger/'
SchemaView = get_schema_view(
    openapi.Info(
        title="Mobile Shop Management System API",
        default_version='v1',
        description="API documentation for Mobile Shop Management System",
        contact=openapi.Contact(email="contact@mobileshop.local"),
        license=openapi.License(name="BSD License"),
    ),
    public=False,
    permission_classes=(permissions.IsAuthenticated,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/inventory/', include('inventory.urls')),
    path('api/sales/', include('sales.urls')),
    path('api/customers/', include('customers.urls')),
    path('api/reports/', include('reports.urls')),
    path('api/', include('settings.urls')),


    # Swagger documentation URLs
    path('swagger/', SchemaView.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),

]

# Serve media files during development
# if settings.DEBUG:
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
