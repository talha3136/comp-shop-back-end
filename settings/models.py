from django.db import models
import uuid


class Shop(models.Model):
    """Model for shop information."""    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)    
    shop_name = models.CharField(max_length=255, help_text='Shop name')
    address = models.TextField(blank=True, null=True, help_text='Shop address')
    phone = models.CharField(max_length=20, blank=True, null=True, help_text='Shop phone')
    email = models.EmailField(blank=True, null=True, help_text='Shop email')
    tax_enabled = models.BooleanField(default=True, help_text='Enable tax calculations')
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=17.00, help_text='Tax percentage')
    
    # Shop status
    is_active = models.BooleanField(default=True, help_text='Is shop active?')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:

        ordering = ['shop_name']

    def __str__(self):
        return self.shop_name