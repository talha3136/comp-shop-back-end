from django.db import models
from django.utils import timezone
import uuid

from config.storages import R2MediaStorage
from utils import customer_profile_image_path, user_profile_image_path

class Customer(models.Model):
    """Model for customers with Khata-style ledger."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Shop relationship
    shop = models.ForeignKey(
        'settings.Shop',
        on_delete=models.CASCADE,
        related_name='customers',
        help_text='Shop this customer belongs to'
    )
    
    name = models.CharField(max_length=100, help_text='Customer name')
    phone = models.CharField(
        max_length=15,
        help_text='Customer phone number'
    )
    email = models.EmailField(blank=True, help_text='Customer email')
    address = models.TextField(blank=True, help_text='Customer address')
    
    # Credit/Debit tracking
    current_balance = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text='Current balance (positive = customer owes, negative = shop owes)'
    )
    
    # Customer stats
    total_purchases = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text='Total purchase amount'
    )
    total_payments = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text='Total payment amount'
    )
    total_outstanding = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text='Total outstanding amount'
    )
    
    # Customer type
    customer_type = models.CharField(
        max_length=20,
        choices=[
            ('regular', 'Regular'),
            ('wholesale', 'Wholesale'),
            ('vip', 'VIP'),
        ],
        default='regular',
        help_text='Customer type'
    )
    
    # Notes
    notes = models.TextField(blank=True, help_text='Customer notes')
    
    # Profile image
    profile_image = models.ImageField(
        upload_to=customer_profile_image_path,
        storage=R2MediaStorage(),
        blank=True,
        null=True,
        help_text='Customer profile picture'
    )
    
    # Status
    is_active = models.BooleanField(default=True, help_text='Is customer active?')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name', '-created_at']
        unique_together = ['shop', 'phone']
    
    def __str__(self):
        return f"{self.name} ({self.phone})"
    
    def get_balance_status(self):
        """Get balance status."""
        if self.current_balance > 0:
            return 'customer_owes'
        elif self.current_balance < 0:
            return 'shop_owes'
        return 'settled'
    
    def get_balance_display(self):
        """Get formatted balance for display."""
        if self.current_balance > 0:
            return f"Owes ₨{self.current_balance}"
        elif self.current_balance < 0:
            return f"Credit ₨{abs(self.current_balance)}"
        return "Settled"

class CustomerTransaction(models.Model):
    """Model for customer transactions (Khata entries)."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    TRANSACTION_TYPE_CHOICES = [
        ('debit', 'Debit'),      # Customer owes more (purchase)
        ('credit', 'Credit'),    # Customer owes less (payment)
    ]
    
    # Shop relationship
    shop = models.ForeignKey(
        'settings.Shop',
        on_delete=models.CASCADE,
        related_name='customer_transactions',
        help_text='Shop this transaction belongs to'
    )
    
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE,
        related_name='transactions',
        help_text='Related customer'
    )
    
    transaction_type = models.CharField(
        max_length=10,
        choices=TRANSACTION_TYPE_CHOICES,
        help_text='Transaction type'
    )
    
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text='Transaction amount'
    )
    
    balance_before = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text='Balance before transaction'
    )
    
    balance_after = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text='Balance after transaction'
    )
    
    # Related records
    sale = models.ForeignKey(
        'sales.Sale', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text='Related sale (for debit transactions)'
    )
    
    description = models.CharField(
        max_length=255, 
        help_text='Transaction description'
    )
    
    transaction_date = models.DateTimeField(default=timezone.now, help_text='Transaction date')
    
    # Staff who recorded the transaction
    recorded_by = models.ForeignKey(
        'accounts.User', 
        on_delete=models.SET_NULL, 
        null=True,
        help_text='Staff who recorded transaction'
    )
    
    # Notes
    notes = models.TextField(blank=True, help_text='Transaction notes')
    
    class Meta:
        ordering = ['-transaction_date', '-id']
    
    def __str__(self):
        return f"{self.customer.name} - {self.transaction_type} ₨{self.amount}"
    
    def save(self, *args, **kwargs):
        """Update customer balance when transaction is created."""
        if not self.pk:  # New transaction
            self.balance_before = self.customer.current_balance
            
            if self.transaction_type == 'debit':
                self.customer.current_balance += self.amount
            elif self.transaction_type == 'credit':
                self.customer.current_balance -= self.amount
            
            self.balance_after = self.customer.current_balance
            self.customer.save()
        
        super().save(*args, **kwargs)

class CustomerDueReport(models.Model):
    """Model for customer due reports."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Shop relationship
    shop = models.ForeignKey(
        'settings.Shop',
        on_delete=models.CASCADE,
        related_name='customer_due_reports',
        help_text='Shop this report belongs to'
    )
    
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE,
        help_text='Related customer'
    )
    
    report_date = models.DateField(help_text='Report date')
    total_outstanding = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text='Total outstanding amount'
    )
    
    days_overdue = models.IntegerField(
        default=0, 
        help_text='Days since last payment'
    )
    
    last_payment_date = models.DateField(
        null=True, 
        blank=True,
        help_text='Date of last payment'
    )
    
    last_purchase_date = models.DateField(
        null=True, 
        blank=True,
        help_text='Date of last purchase'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-total_outstanding', 'customer__name']
        unique_together = ['customer', 'report_date']
    
    def __str__(self):
        return f"{self.customer.name} - ₨{self.total_outstanding} ({self.report_date})"
