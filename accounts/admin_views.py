"""
Super Admin API Views for managing shops and users across the system.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import User, UserPermission
from settings.models import Shop
from .serializers import (
    UserCreateSerializer, UserPermissionSerializer, UserSerializer, UserWithPermissionsSerializer,
    UserPermissionManagementSerializer, SuperAdminTokenObtainPairSerializer
)
from settings.serializers import ShopSerializer, ShopDetailSerializer
from .permissions import IsSuperAdmin
from rest_framework_simplejwt.views import TokenObtainPairView


class SuperAdminTokenObtainPairView(TokenObtainPairView):
    """Custom login view for Super Admins."""
    serializer_class = SuperAdminTokenObtainPairSerializer



class SuperAdminShopViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Super Admin to manage all shops.
    Only accessible by users with super_admin role.
    """
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ShopDetailSerializer
        return ShopSerializer

    def list(self, request):
        """List all shops with statistics"""
        shops = self.get_queryset()
        
        # Add user count and other stats to each shop
        shops_data = []
        for shop in shops:
            shop_data = ShopSerializer(shop).data
            shop_data['user_count'] = shop.users.count()
            shop_data['admin_count'] = shop.users.filter(role='admin').count()
            shop_data['staff_count'] = shop.users.filter(role='staff').count()
            shops_data.append(shop_data)
        
        return Response(shops_data)

    def retrieve(self, request, pk=None):
        """Get detailed shop information with users"""
        shop_id = pk
        shop = get_object_or_404(Shop, id=shop_id)
        serializer = self.get_serializer(shop)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='activate-shop')
    @swagger_auto_schema(
        operation_description="Activate a shop",
        responses={200: 'Shop activated successfully'}
    )
    def activate_shop(self, request, pk=None):
        """Activate a shop"""
        shop_id = pk
        shop = get_object_or_404(Shop, id=shop_id)
        shop.is_active = True
        shop.save()
        return Response({
            'message': f'Shop "{shop.shop_name}" has been activated',
            'shop': ShopSerializer(shop).data
        })

    @action(detail=True, methods=['post'], url_path='deactivate-shop')
    @swagger_auto_schema(
        operation_description="Deactivate a shop",
        responses={200: 'Shop deactivated successfully'}
    )
    def deactivate_shop(self, request, pk=None):
        """Deactivate a shop"""
        shop_id = pk
        shop = get_object_or_404(Shop, id=shop_id)
        shop.is_active = False
        shop.save()
        return Response({
            'message': f'Shop "{shop.shop_name}" has been deactivated',
            'shop': ShopSerializer(shop).data
        })

    @action(detail=True, methods=['get'], url_path='shop-users')
    @swagger_auto_schema(
        operation_description="Get all users for a specific shop",
        responses={200: UserSerializer(many=True)}
    )
    def shop_users(self, request, pk=None):
        """Get all users for a specific shop"""
        shop_id = pk
        shop = get_object_or_404(Shop, id=shop_id)
        users = shop.users.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='system-statistics')
    @swagger_auto_schema(
        operation_description="Get overall system statistics",
        responses={200: 'System statistics'}
    )
    def system_statistics(self, request):
        """Get overall system statistics"""
        total_shops = Shop.objects.count()
        active_shops = Shop.objects.filter(is_active=True).count()
        inactive_shops = Shop.objects.filter(is_active=False).count()
        total_users = User.objects.exclude(role='super_admin').count()
        total_admins = User.objects.filter(role='admin').count()
        total_staff = User.objects.filter(role='staff').count()
        
        # Recent shops (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_shops = Shop.objects.filter(created_at__gte=thirty_days_ago).count()
        
        return Response({
            'total_shops': total_shops,
            'active_shops': active_shops,
            'inactive_shops': inactive_shops,
            'total_users': total_users,
            'total_admins': total_admins,
            'total_staff': total_staff,
            'recent_shops': recent_shops,
        })


class SuperAdminUserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Super Admin to manage all users across all shops.
    Only accessible by users with super_admin role.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def list(self, request):
        """List all users with filtering options"""
        queryset = self.get_queryset()
        
        # Filter by shop if provided
        shop_id = request.query_params.get('shop', None)
        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)
        
        # Filter by role if provided
        role = request.query_params.get('role', None)
        if role:
            queryset = queryset.filter(role=role)
        
        # Filter by active status if provided
        is_active = request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """Get detailed user profile with permissions."""
        user_id = pk
        user = get_object_or_404(User, id=user_id)
        serializer = UserWithPermissionsSerializer(user)
        return Response(serializer.data)

    def update(self, request, pk=None, partial=True):
        print(request.data)
        user = get_object_or_404(User, id=pk)
        serializer = UserWithPermissionsSerializer(user, data=request.data, partial=partial)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    
    @action(detail=True, methods=['post'], url_path='activate-user')
    @swagger_auto_schema(
        operation_description="Activate a user",
        responses={200: 'User activated successfully'}
    )
    def activate_user(self, request, pk=None):
        """Activate a user"""
        user_id = pk
        user = get_object_or_404(User, id=user_id)
        user.is_active = True
        user.save()
        return Response({
            'message': f'User "{user.username}" has been activated',
            'user': UserSerializer(user).data
        })

    @action(detail=True, methods=['post'], url_path='deactivate-user')
    @swagger_auto_schema(
        operation_description="Deactivate a user",
        responses={200: 'User deactivated successfully'}
    )
    def deactivate_user(self, request, pk=None):
        """Deactivate a user"""
        user_id = pk
        user = get_object_or_404(User, id=user_id)
        user.is_active = False
        user.save()
        return Response({
            'message': f'User "{user.username}" has been deactivated',
            'user': UserSerializer(user).data
        })
    
    
    @swagger_auto_schema(
        operation_description="Change user's shop assignment",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'shop_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Shop ID')
            },
            required=['shop_id']
        ),
        responses={200: 'User shop changed successfully', 400: 'Bad request', 404: 'Shop not found'}
    )
    @action(detail=True, methods=['post'], url_path='change-user-shop')

    def change_user_shop(self, request, pk=None):
        """Change user's shop assignment"""
        user_id = pk
        user = get_object_or_404(User, id=user_id)
        shop_id = request.data.get('shop_id')
        
        if not shop_id:
            return Response(
                {'error': 'shop_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            shop = Shop.objects.get(id=shop_id)
            user.shop = shop
            user.save()
            return Response({
                'message': f'User "{user.username}" has been moved to shop "{shop.shop_name}"',
                'user': UserSerializer(user).data
            })
        except Shop.DoesNotExist:
            return Response(
                {'error': 'Shop not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['get'], url_path='user-statistics')
    @swagger_auto_schema(
        operation_description="Get user statistics",
        responses={200: 'User statistics'}
    )
    def user_statistics(self, request):
        """Get user statistics"""
        total_users = self.get_queryset().count()
        active_users = self.get_queryset().filter(is_active=True).count()
        inactive_users = self.get_queryset().filter(is_active=False).count()
        admins = self.get_queryset().filter(role='admin').count()
        staff = self.get_queryset().filter(role='staff').count()
        
        return Response({
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': inactive_users,
            'admins': admins,
            'staff': staff,
        })

    @action(
        detail=True,
        url_path='login-as-user',
        methods=['post'])
    @swagger_auto_schema(
        operation_description="Login as this user without credentials",
        responses={200: 'Login successful', 400: 'User is inactive'}
    )
    def login_as_user(self, request, pk=None):
        """
        Login as this user without credentials.
        Returns access and refresh tokens for the target user.
        """
        user_id = pk
        user = get_object_or_404(User, id=user_id)

        if not user.is_active:
             return Response({'error': 'User is inactive'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate tokens manually
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        })



    @action(detail=True, methods=['post'], url_path='manage-user-permissions')
    @swagger_auto_schema(
        operation_description="Manage user permissions",
        request_body=UserPermissionManagementSerializer,
        responses={200: 'Permissions updated successfully', 400: 'Bad request'}
    )
    def manage_user_permissions(self, request, pk=None):
        """Manage user permissions."""
        user_id = pk
        user = get_object_or_404(User, id=user_id)
        serializer = UserPermissionManagementSerializer(data=request.data)

        if serializer.is_valid():
            permissions_to_assign = serializer.validated_data['permissions']

            # Remove all existing permissions for this user
            user.permissions.all().delete()

            # Create new permissions
            permissions_to_create = []
            for permission_code in permissions_to_assign:
                permissions_to_create.append(UserPermission(
                    user=user,
                    permission=permission_code,
                    granted_by=request.user
                ))

            UserPermission.objects.bulk_create(permissions_to_create)

            return Response({
                'message': f'Permissions updated for user "{user.username}"',
                'user': UserWithPermissionsSerializer(user).data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='user-permissions')
    @swagger_auto_schema(
        operation_description="Get user's permissions",
        responses={200: 'User permissions'}
    )
    def user_permissions(self, request, pk=None):
        """Get user's permissions."""
        user_id = pk
        user = get_object_or_404(User, id=user_id)
        permissions = user.permissions.all()
        serializer = UserPermissionSerializer(permissions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='available-permissions')
    @swagger_auto_schema(
        operation_description="Get all available permission choices",
        responses={200: 'Available permissions'}
    )
    def available_permissions_list(self, request):
        """Get all available permission choices."""
        permissions = [
            {'code': choice[0], 'name': choice[1]}
            for choice in UserPermission.PERMISSION_CHOICES
        ]
        return Response(permissions)


class ShopAdminUserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Shop Admin to manage users within their own shop.
    Only accessible by users with admin role (shop admins).
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Only return users from the current admin's shop"""
        if not self.request.user.is_admin():
            return User.objects.none()
        return User.objects.filter(shop=self.request.user.shop)

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return UserCreateSerializer
        return UserSerializer

    def create(self, request):
        """Create a new user for the shop admin's shop."""
        # Ensure shop is set to the current admin's shop
        request.data['shop'] = request.user.shop.id

        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # Create audit log entry for user creation
            from logs.models import AuditLog
            AuditLog.objects.create(
                user=request.user,
                action='user_created',
                resource_type='user',
                resource_id=user.id,
                details=f'Created user "{user.username}" with role "{user.role}" for shop "{user.shop.shop_name}"',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )

            return Response({
                'message': f'User "{user.username}" created successfully',
                'user': UserWithPermissionsSerializer(user).data
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        """Update user information."""
        user = self.get_object()

        # Ensure shop admin can only update users in their shop
        if user.shop != request.user.shop:
            return Response(
                {'error': 'You can only manage users in your own shop'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = UserCreateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            updated_user = serializer.save()

            # Create audit log entry for user update
            from logs.models import AuditLog
            AuditLog.objects.create(
                user=request.user,
                action='user_updated',
                resource_type='user',
                resource_id=updated_user.id,
                details=f'Updated user "{updated_user.username}" in shop "{updated_user.shop.shop_name}"',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )

            return Response({
                'message': f'User "{updated_user.username}" updated successfully',
                'user': UserWithPermissionsSerializer(updated_user).data
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a user"""
        user = self.get_object()
        user.is_active = True
        user.save()

        # Create audit log
        from logs.models import AuditLog
        AuditLog.objects.create(
            user=request.user,
            action='user_activated',
            resource_type='user',
            resource_id=user.id,
            details=f'Activated user "{user.username}"',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )

        return Response({
            'message': f'User "{user.username}" has been activated',
            'user': UserSerializer(user).data
        })

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a user"""
        user = self.get_object()
        user.is_active = False
        user.save()

        # Create audit log
        from logs.models import AuditLog
        AuditLog.objects.create(
            user=request.user,
            action='user_deactivated',
            resource_type='user',
            resource_id=user.id,
            details=f'Deactivated user "{user.username}"',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )

        return Response({
            'message': f'User "{user.username}" has been deactivated',
            'user': UserSerializer(user).data
        })

    @action(detail=True, methods=['get'])
    def permissions(self, request, pk=None):
        """Get user's permissions."""
        user = self.get_object()
        permissions = user.permissions.all()
        serializer = UserPermissionSerializer(permissions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def manage_permissions(self, request, pk=None):
        """Manage user permissions."""
        user = self.get_object()
        serializer = UserPermissionManagementSerializer(data=request.data)

        if serializer.is_valid():
            permissions_to_assign = serializer.validated_data['permissions']

            # Remove all existing permissions for this user
            user.permissions.all().delete()

            # Create new permissions
            permissions_to_create = []
            for permission_code in permissions_to_assign:
                permissions_to_create.append(UserPermission(
                    user=user,
                    permission=permission_code,
                    granted_by=request.user
                ))

            UserPermission.objects.bulk_create(permissions_to_create)

            # Create audit log
            from logs.models import AuditLog
            AuditLog.objects.create(
                user=request.user,
                action='permission_granted',
                resource_type='permission',
                resource_id=user.id,
                details=f'Updated permissions for user "{user.username}"',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )

            return Response({
                'message': f'Permissions updated for user "{user.username}"',
                'user': UserWithPermissionsSerializer(user).data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
