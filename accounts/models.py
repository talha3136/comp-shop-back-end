from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid

from config.storages import R2MediaStorage
from utils import user_profile_image_path

class User(AbstractUser):
    """Custom user model with role-based access control."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('admin', 'Admin'),
        ('staff', 'Staff'),
    ]
    
    # Shop relationship
    shop = models.ForeignKey(
        'settings.Shop',
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True,
        help_text='Shop this user belongs to'
    )
    
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='super_admin',
        help_text='User role determines access level'
    )
    
    phone = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text='Contact phone number'
    )
    
    # Profile image
    profile_image = models.ImageField(
        upload_to=user_profile_image_path,
        storage=R2MediaStorage(),
        blank=True,
        null=True,
        help_text='User profile picture'
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text='Designates whether this user should be treated as active'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.username} ({self.role})"
    
    def is_super_admin(self):
        return self.role == 'super_admin'
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_staff_user(self):
        return self.role == 'staff'
    
    def has_full_access(self):
        return self.is_admin() or self.is_super_admin()
    
    def is_shop_admin(self):
        """Returns True if user is admin of a specific shop"""
        return self.role == 'admin' and self.shop is not None

    def has_permission(self, permission):
        """Check if user has a specific permission."""
        if self.is_super_admin():
            return True  # Super admin has all permissions

        # Check if user has the specific permission
        return self.permissions.filter(permission=permission).exists()

    def has_any_permission(self, permissions):
        """Check if user has any of the specified permissions."""
        if self.is_super_admin():
            return True  # Super admin has all permissions

        return self.permissions.filter(permission__in=permissions).exists()

    def get_all_permissions(self):
        """Get all permissions for this user."""
        if self.is_super_admin():
            # Return all available permissions for super admin
            return [choice[0] for choice in UserPermission.PERMISSION_CHOICES]

        return list(self.permissions.values_list('permission', flat=True))


class UserPermission(models.Model):
    """Granular permissions for users beyond basic roles."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    PERMISSION_CHOICES = [
        # User Management
        ('manage_users', 'Manage Users'),
        ('view_users', 'View Users'),
        ('create_users', 'Create Users'),
        ('edit_users', 'Edit Users'),
        ('delete_users', 'Delete Users'),

        # Shop Management
        ('manage_shops', 'Manage Shops'),
        ('view_shops', 'View Shops'),
        ('create_shops', 'Create Shops'),
        ('edit_shops', 'Edit Shops'),
        ('delete_shops', 'Delete Shops'),

        # Inventory Management
        ('manage_inventory', 'Manage Inventory'),
        ('view_inventory', 'View Inventory'),
        ('create_inventory', 'Create Inventory'),
        ('edit_inventory', 'Edit Inventory'),
        ('delete_inventory', 'Delete Inventory'),

        # Sales Management
        ('manage_sales', 'Manage Sales'),
        ('view_sales', 'View Sales'),
        ('create_sales', 'Create Sales'),
        ('edit_sales', 'Edit Sales'),
        ('delete_sales', 'Delete Sales'),

        # Reports
        ('view_reports', 'View Reports'),
        ('manage_reports', 'Manage Reports'),

        # Settings
        ('manage_settings', 'Manage Settings'),
        ('view_settings', 'View Settings'),

        # All Permissions (for super admin)
        ('all_permissions', 'All Permissions'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='permissions'
    )
    permission = models.CharField(
        max_length=50,
        choices=PERMISSION_CHOICES,
        help_text='Specific permission granted to this user'
    )
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='granted_permissions',
        help_text='User who granted this permission'
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'permission']
        verbose_name = 'User Permission'
        verbose_name_plural = 'User Permissions'
        ordering = ['-granted_at']

    def __str__(self):
        return f"{self.user.username} - {self.permission}"
