from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from .models import User, UserPermission
from settings.models import Shop

# Serializer for User model
# Fields included: Basic user info for authentication and profile display (id, username, email, first_name, last_name, phone, role, is_active) - excludes internal timestamps and password fields as not needed for frontend display.
class UserSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source='shop.shop_name', read_only=True)


    class Meta:
        model = User
        fields = '__all__'
class UserDetailSerializer(serializers.ModelSerializer):
    """Detailed user serializer for superadmin profile management."""
    shop_name = serializers.CharField(source='shop.shop_name', read_only=True)

    full_name = serializers.SerializerMethodField()
    last_login = serializers.DateTimeField(read_only=True)
    date_joined = serializers.DateTimeField(read_only=True)

    class Meta:
        model = User
        fields = '__all__'
        
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer with additional user info."""
    
    def validate(self, attrs):
        """Validate user credentials and return tokens with user data."""
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            user = authenticate(username=username, password=password)
            
            if user:
                if not user.is_active:
                    raise serializers.ValidationError('User account is disabled.')
                
                data = super().validate(attrs)
                data['user'] = UserSerializer(user).data
                return data
            else:
                raise serializers.ValidationError('Invalid credentials')
        else:
            raise serializers.ValidationError('Username and password required')

class SuperAdminTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer strictly for Super Admin login."""
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            user = authenticate(username=username, password=password)
            
            if user:
                if not user.is_active:
                    raise serializers.ValidationError('User account is disabled.')
                
                if not (user.role == 'super_admin' or user.is_superuser):
                    raise serializers.ValidationError('Access denied. Super Admin privileges required.')
                
                data = super().validate(attrs)
                data['user'] = UserSerializer(user).data
                return data
            else:
                raise serializers.ValidationError('Invalid credentials')
        else:
            raise serializers.ValidationError('Username and password required')


class ChangeUserPasswordSerializer(serializers.Serializer):
    """Serializer for password change."""
    
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(required=True, write_only=True, min_length=8)
    
    def validate(self, attrs):
        """Validate password change data."""
        if attrs.get('new_password') != attrs.get('new_password_confirm'):
            raise serializers.ValidationError("New passwords don't match")
        return attrs
    
    def validate_old_password(self, value):
        """Validate old password."""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Old password is incorrect')
        return value

class ChangePasswordSerializer(serializers.Serializer):

    new_password = serializers.CharField(required=True, write_only=True, min_length=8)
    confirm_password = serializers.CharField(required=True, write_only=True, min_length=8)
    
    def validate(self, attrs):
        """Validate password change data."""
        if attrs.get('new_password') != attrs.get('confirm_password'):
            raise serializers.ValidationError("New passwords don't match")
        return attrs

class StaffUserSerializer(serializers.ModelSerializer):
    """Serializer for staff users (limited fields)."""

    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name',
            'phone', 'role', 'is_active'
        ]
        read_only_fields = ['id', 'role']

class UserPermissionSerializer(serializers.ModelSerializer):
    """Serializer for user permissions."""
    permission_display = serializers.CharField(source='get_permission_display', read_only=True)
    granted_by_username = serializers.CharField(source='granted_by.username', read_only=True)

    class Meta:
        model = UserPermission
        fields = [
            'id', 'permission', 'permission_display',
            'granted_by', 'granted_by_username', 'granted_at'
        ]
        read_only_fields = ['id', 'granted_at']

class UserWithPermissionsSerializer(serializers.ModelSerializer):
    """Detailed user serializer with permissions for superadmin management."""
    shop_name = serializers.CharField(source='shop.shop_name', read_only=True)
    full_name = serializers.SerializerMethodField()
    permissions = UserPermissionSerializer(many=True, read_only=True)
    all_permissions = serializers.SerializerMethodField()
    last_login = serializers.DateTimeField(read_only=True)
    date_joined = serializers.DateTimeField(read_only=True)

    class Meta:
        model = User
        fields = '__all__'

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

    def get_all_permissions(self, obj):
        """Return all permissions this user has."""
        return obj.get_all_permissions()

class UserPermissionManagementSerializer(serializers.Serializer):
    """Serializer for managing user permissions."""
    permissions = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        help_text='List of permission codes to assign to the user'
    )

    def validate_permissions(self, value):
        """Validate that all permissions are valid."""
        from .models import UserPermission
        valid_permissions = [choice[0] for choice in UserPermission.PERMISSION_CHOICES]
        invalid_permissions = [p for p in value if p not in valid_permissions]
        if invalid_permissions:
            raise serializers.ValidationError(f"Invalid permissions: {', '.join(invalid_permissions)}")
        return value

class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating users by super admin."""
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, required=True)
    shop = serializers.PrimaryKeyRelatedField(queryset=Shop.objects.all(), required=True)
    shop_name = serializers.CharField(source='shop.shop_name', read_only=True)
    permissions = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text='List of permission codes to assign to the user'
    )

    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name', 'phone',
            'role', 'shop', 'shop_name', 'password', 'password_confirm',
            'permissions', 'is_active'
        ]
        extra_kwargs = {
            'is_active': {'default': True, 'required': False}
        }

    def validate(self, attrs):
        """Validate user creation data."""
        # Check password confirmation
        if attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match'})

        # Validate permissions if provided
        permissions = attrs.get('permissions', [])
        if permissions:
            valid_permissions = [choice[0] for choice in UserPermission.PERMISSION_CHOICES]
            invalid_permissions = [p for p in permissions if p not in valid_permissions]
            if invalid_permissions:
                raise serializers.ValidationError({
                    'permissions': f"Invalid permissions: {', '.join(invalid_permissions)}"
                })

        # Super admin cannot be created through this endpoint
        if attrs.get('role') == 'super_admin':
            raise serializers.ValidationError({'role': 'Super Admin users cannot be created through this endpoint'})

        return attrs

    def create(self, validated_data):
        """Create user with hashed password and permissions."""
        permissions = validated_data.pop('permissions', [])
        password_confirm = validated_data.pop('password_confirm')

        # Hash the password
        validated_data['password'] = make_password(validated_data['password'])

        # Create the user
        user = super().create(validated_data)

        # Assign permissions if provided
        if permissions:
            permissions_to_create = []
            for permission_code in permissions:
                permissions_to_create.append(UserPermission(
                    user=user,
                    permission=permission_code,
                    granted_by=self.context['request'].user
                ))
            UserPermission.objects.bulk_create(permissions_to_create)

        return user
