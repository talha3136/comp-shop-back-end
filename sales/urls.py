from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SaleViewSet, SalePaymentViewSet

router = DefaultRouter()
router.register(r'', SaleViewSet, basename='sale')
router.register(r'sale-payments', SalePaymentViewSet, basename='sale-payment')




urlpatterns = [
    path('', include(router.urls)),
]
