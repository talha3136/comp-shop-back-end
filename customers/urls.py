from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomerViewSet, CustomerTransactionViewSet

router = DefaultRouter()
router.register(r'', CustomerViewSet, basename='customer')
router.register(r'transactions', CustomerTransactionViewSet, basename='transaction')

urlpatterns = [
    path('', include(router.urls)),
]
