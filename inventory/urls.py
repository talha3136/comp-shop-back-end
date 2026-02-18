from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductViewSet, ProductPurchaseViewSet, ComputerPurchaseViewSet,
    SupplierViewSet, ComputerRepairViewSet,
    ComputerBrandViewSet, ComputerModelViewSet, CategoryViewSet, DashboardStatsView,
    UnifiedSearchViewSet, ComputerImageViewSet
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'product-purchases', ProductPurchaseViewSet, basename='product-purchase')
router.register(r'computer-purchases', ComputerPurchaseViewSet, basename='computer-purchase')
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'repairs', ComputerRepairViewSet, basename='repair')
router.register(r'brands', ComputerBrandViewSet, basename='brand')
router.register(r'models', ComputerModelViewSet, basename='model')
router.register(r'computer-images', ComputerImageViewSet, basename='computer-image')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard-stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('search/', UnifiedSearchViewSet.as_view({'get': 'list'}), name='unified-search'),
]
