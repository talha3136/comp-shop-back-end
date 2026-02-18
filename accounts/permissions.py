from rest_framework import permissions

class IsAdminUser(permissions.BasePermission):
    """Custom permission to only allow admin users."""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'admin'

class IsStaffUser(permissions.BasePermission):
    """Custom permission to only allow staff and admin users."""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role in ['admin', 'staff']

class IsOwnerOrAdmin(permissions.BasePermission):
    """Custom permission to only allow owners of an object or admin users."""
    
    def has_object_permission(self, request, view, obj):
        # Admin users can access any object
        if request.user.role == 'admin':
            return True
        
        # Check if the object has a user attribute and matches the current user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Check if the object is the user itself
        if hasattr(obj, 'id') and hasattr(request.user, 'id'):
            return obj.id == request.user.id
            
        return False

class IsSuperAdmin(permissions.BasePermission):
    """Custom permission to only allow super admin users."""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'super_admin'

