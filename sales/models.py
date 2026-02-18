from django.db import models
from django.conf import settings
import uuid

class Sale(models.Model):
    """Model for sales transactions."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('credit', 'Credit'),
        ('bank_transfer', 'Bank Transfer'),
    ]
    
    # Shop relationship
    shop = models.ForeignKey(
        'settings.Shop',
        on_delete=models.CASCADE,
        related_name='sales',
        help_text='Shop this sale belongs to'
    )
    
    # Basic sale info
    sale_number = models.CharField(
        max_length=50, 
        unique=True, 
        blank=True, 
        help_text='Auto-generated sale number'
    )
    sale_date = models.DateTimeField(auto_now_add=True)
    
    # Customer info
    customer_name = models.CharField(
        max_length=100, 
        blank=True,
        default='Walk-in Customer',
        help_text='Walk-in customer name'
    )
    customer_phone = models.CharField(
        max_length=15, 
        blank=True,
        default='N/A',
        help_text='Customer phone number'
    )
    
    # Link to customer account if exists
    customer = models.ForeignKey(
        'customers.Customer', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text='Linked customer account'
    )
    
    # Staff who made the sale
    sold_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        help_text='Staff member who made the sale'
    )
    
    # Sale items and totals
    subtotal = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text='Subtotal before discount and tax'
    )
    discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text='Discount amount'
    )
    tax_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text='Tax amount'
    )
    total_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text='Final total amount'
    )
    
    # Payment info
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='cash',
        help_text='Payment method used'
    )
    amount_paid = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text='Amount paid by customer'
    )
    change_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text='Change given to customer'
    )
    
    # Profit tracking
    total_profit = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text='Total profit from this sale'
    )
    
    # Status
    is_completed = models.BooleanField(default=True, help_text='Is sale completed?')
    is_cancelled = models.BooleanField(default=False, help_text='Is sale cancelled?')
    
    # Notes
    notes = models.TextField(blank=True, help_text='Sale notes or comments')
    
    # Receipt info
    receipt_printed = models.BooleanField(default=False, help_text='Has receipt been printed?')
    receipt_number = models.CharField(
        max_length=50, 
        blank=True, 
        help_text='Receipt number for thermal printer'
    )
    
    class Meta:
        ordering = ['-sale_date']
    
    def __str__(self):
        date_str = self.sale_date.strftime('%Y-%m-%d %H:%M') if self.sale_date else 'Unsaved'
        return f"Sale #{self.sale_number or 'Unsaved'} - {date_str}"
    
    def save(self, *args, **kwargs):
        """Generate sale number if not exists."""
        if not self.sale_number:
            # Ensure sale_date is set before generating sale number
            if not self.sale_date:
                from django.utils import timezone
                self.sale_date = timezone.now()
            self.sale_number = f"SALE-{self.sale_date.strftime('%Y%m%d%H%M%S')}"
        super().save(*args, **kwargs)
    
    def calculate_totals(self):
        """Calculate subtotal, total, and profit from sale items."""
        items = self.sale_items.all()
        
        subtotal = 0
        total_profit = 0
        
        for item in items:
            subtotal += item.total_price
            total_profit += item.profit
        
        self.subtotal = subtotal
        self.total_profit = total_profit
        
        # Apply discount
        if self.discount_amount:
            subtotal -= self.discount_amount
        
        # Apply tax (assuming 17% GST as default)
        if subtotal > 0:
            self.tax_amount = subtotal * 0.17
            self.total_amount = subtotal + self.tax_amount
        else:
            self.total_amount = subtotal
        
        # Calculate change
        if self.amount_paid > self.total_amount:
            self.change_amount = self.amount_paid - self.total_amount
        
        self.save()
    
    def print_receipt(self):
        """Mark receipt as printed."""
        self.receipt_printed = True
        self.save()
    
    def get_stock_restoration_summary(self):
        """Get summary of stock that will be restored if sale is cancelled."""
        summary = []
        for item in self.sale_items.all():
            if item.computer_purchase:
                summary.append({
                    'product_name': item.product_name,
                    'batch_number': f'Computer S/N: {item.computer_purchase.serial_number}',
                    'quantity_to_restore': item.quantity,
                    'current_stock': 'Sold' if item.computer_purchase.sold else 'In Stock',
                    'restored_stock': 'In Stock'
                })
            elif item.product_purchase:
                summary.append({
                    'product_name': item.product_name,
                    'batch_number': item.product_purchase.batch_number or f'Batch #{item.product_purchase.id}',
                    'quantity_to_restore': item.quantity,
                    'current_stock': item.product_purchase.remaining_quantity,
                    'restored_stock': item.product_purchase.remaining_quantity + item.quantity
                })
            elif item.product:
                summary.append({
                    'product_name': item.product_name,
                    'batch_number': 'To be determined',
                    'quantity_to_restore': item.quantity,
                    'current_stock': 'N/A',
                    'restored_stock': 'N/A'
                })
        return summary

class SaleItem(models.Model):
    """Model for individual items in a sale."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Shop relationship
    shop = models.ForeignKey(
        'settings.Shop',
        on_delete=models.CASCADE,
        related_name='sale_items',
        help_text='Shop this sale item belongs to'
    )
    
    sale = models.ForeignKey(
        Sale, 
        on_delete=models.CASCADE,
        related_name='sale_items',
        help_text='Related sale'
    )
    
    # Product info
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Product'
    )
    product_purchase = models.ForeignKey(
        'inventory.ProductPurchase',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Product purchase batch (for batch tracking)'
    )
    computer_purchase = models.ForeignKey(
        'inventory.ComputerPurchase',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Computer purchase (for computer sales)'
    )
    product_name = models.CharField(
        max_length=255,
        help_text='Product name at time of sale'
    )
    product_item_code = models.CharField(
        max_length=50,
        blank=True,
        help_text='Product item code at time of sale'
    )
    
    # Pricing
    unit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text='Unit price at time of sale'
    )
    quantity = models.PositiveIntegerField(default=1, help_text='Quantity sold')
    total_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text='Total price for this item'
    )
    
    # Profit tracking
    cost_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text='Cost price at time of sale'
    )
    profit = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text='Profit from this item'
    )
    
    class Meta:
        ordering = ['id']
    
    def __str__(self):
        return f"{self.product_name} x{self.quantity} - Sale #{self.sale.sale_number}"
    
    def save(self, *args, **kwargs):
        """Calculate total price and profit."""
        self.total_price = self.unit_price * self.quantity
        self.profit = (self.unit_price - self.cost_price) * self.quantity
        super().save(*args, **kwargs)
    
    def restore_stock(self):
        """Restore product stock when sale is cancelled."""
        if self.computer_purchase:
            # Mark computer as not sold
            self.computer_purchase.sold = False
            self.computer_purchase.save(update_fields=['sold'])
        elif self.product_purchase:
            # Restore stock to the specific batch using safe adjustment
            self.product_purchase.adjust_stock(
                quantity_change=self.quantity,
                reason=f"Sale cancellation - {self.sale.sale_number}"
            )
        elif self.product:
            # If no specific batch, find the most recent batch with remaining stock
            from inventory.models import ProductPurchase
            latest_batch = ProductPurchase.objects.filter(
                product=self.product,
                remaining_quantity__gt=0
            ).order_by('-purchase_date').first()

            if latest_batch:
                latest_batch.adjust_stock(
                    quantity_change=self.quantity,
                    reason=f"Sale cancellation - {self.sale.sale_number}"
                )
            else:
                # If no batch found, create a new batch entry
                ProductPurchase.objects.create(
                    product=self.product,
                    purchase_date=self.sale.sale_date.date(),
                    batch_number=f"RESTORE-{self.sale.sale_number}",
                    purchase_price=self.cost_price,
                    selling_price=self.unit_price,
                    quantity=self.quantity,
                    remaining_quantity=self.quantity
                )
    

class SalePayment(models.Model):
    """Model for tracking payments against sales (for credit sales)."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Shop relationship
    shop = models.ForeignKey(
        'settings.Shop',
        on_delete=models.CASCADE,
        related_name='sale_payments',
        help_text='Shop this payment belongs to'
    )
    
    sale = models.ForeignKey(
        Sale, 
        on_delete=models.CASCADE,
        related_name='payments',
        help_text='Related sale'
    )
    
    amount_paid = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text='Amount paid'
    )
    
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(
        max_length=20,
        choices=Sale.PAYMENT_METHOD_CHOICES,
        default='cash',
        help_text='Payment method'
    )
    
    notes = models.TextField(blank=True, help_text='Payment notes')
    
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True,
        help_text='Staff who received payment'
    )
    
    class Meta:
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Payment of {self.amount_paid} for Sale #{self.sale.sale_number}"
