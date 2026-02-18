from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import CustomTokenObtainPairView, UserViewSet
from .admin_views import SuperAdminShopViewSet, SuperAdminUserViewSet, SuperAdminTokenObtainPairView, ShopAdminUserViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

# Super Admin routes
superadmin_router = DefaultRouter()
superadmin_router.register(r'shops', SuperAdminShopViewSet, basename='superadmin-shop')
superadmin_router.register(r'all-users', SuperAdminUserViewSet, basename='superadmin-user')

# Shop Admin routes
shopadmin_router = DefaultRouter()
shopadmin_router.register(r'users', ShopAdminUserViewSet, basename='shopadmin-user')

urlpatterns = [
    # Authentication endpoints
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Super Admin endpoints
    path('superadmin/login/', SuperAdminTokenObtainPairView.as_view(), name='super_admin_login'),
    path('superadmin/', include(superadmin_router.urls)),

    # Shop Admin endpoints
    path('shop-admin/', include(shopadmin_router.urls)),

    # Include router URLs
    path('', include(router.urls)),
]
