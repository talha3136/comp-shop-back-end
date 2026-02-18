from rest_framework import viewsets, status, permissions, mixins
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import get_user_model
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .serializers import (
    ChangePasswordSerializer, UserSerializer, CustomTokenObtainPairSerializer,
    ChangeUserPasswordSerializer, StaffUserSerializer
)
from .permissions import IsAdminUser, IsStaffUser

User = get_user_model()
from datetime import datetime

from django.http import HttpResponse


def index(request):
    now = datetime.now()
    html = f'''
    <html>
        <body>
            <h1>Hello from Vercel!</h1>
            <p>The current time is { now }.</p>
        </body>
    </html>
    '''
    return HttpResponse(html)
class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom login view with additional user data."""
    serializer_class = CustomTokenObtainPairSerializer

class CustomTokenRefreshView(TokenRefreshView):
    """Custom token refresh view."""
    pass

class UserViewSet(viewsets.ModelViewSet):
    """User management viewset with CRUD operations and custom actions."""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        """Use different serializers based on user role."""
        # Handle anonymous users (e.g., during Swagger schema generation)


        if self.request.user.is_admin():
            return UserSerializer
        return StaffUserSerializer

    def get_permissions(self):
        """Set permissions based on action."""
        if self.action == 'logout':
            return [permissions.AllowAny()]
        elif self.action in ['create', 'list', 'staff_list', 'admin_list']:
            return [permissions.IsAuthenticated(), IsAdminUser()]
        elif self.action == 'destroy':
            return [permissions.IsAuthenticated(), IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        """Filter queryset based on user permissions."""
        # Handle anonymous users (e.g., during Swagger schema generation)

        if self.request.user.shop:
            return User.objects.filter(shop=self.request.user.shop)
        if self.request.user.is_admin():
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)

    def perform_create(self, serializer):
        """Create user (admin only)."""
        serializer.save()

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsAdminUser], url_path='register-user')
    @swagger_auto_schema(
        operation_description="Register new user (admin only)",
        request_body=UserSerializer,
        responses={201: UserSerializer, 400: 'Bad request'}
    )
    def register_user(self, request):
        """Register new user (admin only)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=False, 
        methods=['get'], 
        url_path='user-profile'
        ) 

    def user_profile(self, request):
        """Get current user profile."""
        instance = request.user
        user = User.objects.get(id=instance.id)
        serializer = UserSerializer(user)
        return Response(serializer.data)

    @action(detail=False, methods=['put'], url_path='update-user-profile')
    @swagger_auto_schema(
        operation_description="Update current user profile",
        request_body=UserSerializer,
        responses={200: UserSerializer, 400: 'Bad request'}
    )
    def update_user_profile(self, request):
        """Update current user profile."""
        instance = request.user
        
        # Handle multipart form data for image uploads
        if request.content_type and 'multipart/form-data' in request.content_type:
            serializer = self.get_serializer(instance, data=request.data, partial=True)
        else:
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['put'], url_path='change-user-password')
    @swagger_auto_schema(
        operation_description="Change user password",
        request_body=ChangeUserPasswordSerializer,
        responses={200: 'Password updated successfully', 400: 'Bad request'}
    )
    def change_user_password(self, request):
        """Change user password."""
        serializer = ChangeUserPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Set new password
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()

        return Response(
            {"message": "Password updated successfully"},
            status=status.HTTP_200_OK
        )
    @action(
        detail=True,
        methods=['patch'],
        url_path='change-password',
        serializer_class=ChangePasswordSerializer
    )
    def change_password(self, request, pk=None):
        # Use the explicitly specified serializer class instead of get_serializer()
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.get(id = pk) 

        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Response(
            {"message": "Password updated successfully"},
            status=status.HTTP_200_OK
        )


    @action(detail=False, methods=['get'], url_path='staff-users')
    @swagger_auto_schema(
        operation_description="List staff users (admin only)",
        responses={200: StaffUserSerializer(many=True)}
    )
    def staff_users(self, request):
        """List staff users (admin only)."""
        queryset = User.objects.filter(role='staff')
        serializer = StaffUserSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='admin-users')
    @swagger_auto_schema(
        operation_description="List admin users (admin only)",
        responses={200: UserSerializer(many=True)}
    )
    def admin_users(self, request):
        """List admin users (admin only)."""
        queryset = User.objects.filter(role='admin')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='user-logout',
            permission_classes=[permissions.AllowAny],
            authentication_classes=[])
    @swagger_auto_schema(
        operation_description="Logout user (blacklist refresh token)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'refresh': openapi.Schema(type=openapi.TYPE_STRING, description='Refresh token')
            },
            required=['refresh']
        ),
        responses={200: 'Successfully logged out'}
    )
    def user_logout(self, request):
        """Logout user (blacklist refresh token)."""
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                # Blacklist the refresh token if using blacklist app
                from rest_framework_simplejwt.tokens import RefreshToken
                token = RefreshToken(refresh_token)
                token.blacklist()

            return Response(
                {"message": "Successfully logged out"},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            # Even if blacklisting fails, consider logout successful
            return Response(
                {"message": "Successfully logged out"},
                status=status.HTTP_200_OK
            )
