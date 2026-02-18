from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class AuditLog(models.Model):
    """Model for tracking audit logs of system actions."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ACTION_CHOICES = [
        ('user_created', 'User Created'),
        ('user_updated', 'User Updated'),
        ('user_deleted', 'User Deleted'),
        ('user_activated', 'User Activated'),
        ('user_deactivated', 'User Deactivated'),
        ('permission_granted', 'Permission Granted'),
        ('permission_revoked', 'Permission Revoked'),
        ('shop_created', 'Shop Created'),
        ('shop_updated', 'Shop Updated'),
        ('shop_deleted', 'Shop Deleted'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('password_changed', 'Password Changed'),
    ]

    RESOURCE_TYPE_CHOICES = [
        ('user', 'User'),
        ('shop', 'Shop'),
        ('permission', 'Permission'),
        ('system', 'System'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text='User who performed the action'
    )
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        help_text='Type of action performed'
    )
    resource_type = models.CharField(
        max_length=20,
        choices=RESOURCE_TYPE_CHOICES,
        help_text='Type of resource affected'
    )
    resource_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='ID of the affected resource'
    )
    details = models.TextField(
        blank=True,
        help_text='Additional details about the action'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text='IP address of the user'
    )
    user_agent = models.TextField(
        blank=True,
        help_text='User agent string'
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['user', 'action']),
            models.Index(fields=['resource_type', 'resource_id']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else 'System'
        return f"{user_str} - {self.action} - {self.timestamp}"
