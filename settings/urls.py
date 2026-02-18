from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import ShopViewSet

router = DefaultRouter()
router.register(r'shops', ShopViewSet)

# Compatibility endpoint for frontend
urlpatterns = [
    path('shop-settings/current/', ShopViewSet.as_view({'get': 'current', 'put': 'update_current', 'patch': 'update_current'}), name='shop-settings-current'),
] + router.urls