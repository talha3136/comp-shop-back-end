import uuid
from decimal import Decimal
from django.db import models
from django.db.models import Sum
from django.utils.text import slugify
from PIL import Image

from config.storages import R2MediaStorage
from utils import computer_image_path, computer_purchase_photo_path


class Category(models.Model):
    """Model for product categories."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Shop relationship
    shop = models.ForeignKey(
        'settings.Shop',
        on_delete=models.CASCADE,
        related_name='categories',
        null=True,
        blank=True,
        help_text='Shop this category belongs to'
    )
    
    name = models.CharField(
        max_length=100,
        help_text='Category name'
    )
    description = models.TextField(
        blank=True,
        help_text='Category description'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Is category active?'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Categories'
        unique_together = ['shop', 'name']
    
    def __str__(self):
        return self.name


class Product(models.Model):
    """Model for general products (non-mobile items)."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Shop relationship
    shop = models.ForeignKey(
        'settings.Shop',
        on_delete=models.CASCADE,
        related_name='products',
        null=True,
        blank=True,
        help_text='Shop this product belongs to'
    )

    name = models.CharField(max_length=255, help_text='Product name')
    item_code = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        help_text='Auto-generated item code'
    )
    description = models.TextField(blank=True, help_text='Product description')

    # Stock management - now computed from purchases
    min_stock_level = models.PositiveIntegerField(
        default=5,
        help_text='Minimum stock level for alerts'
    )

    # Category
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Product category'
    )

    # Status
    is_active = models.BooleanField(default=True, help_text='Is product active?')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name', '-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.item_code})"
    
    def save(self, *args, **kwargs):
        """Generate item code if not exists."""
        if not self.item_code:
            self.item_code = f"PRD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    def is_low_stock(self):
        """Check if product is low on stock."""
        return self.stock_quantity <= self.min_stock_level
    
    @property
    def stock_quantity(self):
        """Calculate total stock from all purchases."""
        return self.purchases.filter(remaining_quantity__gt=0).aggregate(
            total=Sum('remaining_quantity')
        )['total'] or 0

    @property
    def cost_price(self):
        """Get latest purchase cost price."""
        latest_purchase = self.purchases.filter(remaining_quantity__gt=0).order_by('-purchase_date').first()
        return latest_purchase.purchase_price if latest_purchase else 0

    @property
    def selling_price(self):
        """Get latest selling price."""
        latest_purchase = self.purchases.filter(remaining_quantity__gt=0).order_by('-purchase_date').first()
        return latest_purchase.selling_price if latest_purchase else 0

    def get_profit_margin(self):
        """Calculate profit margin percentage."""
        if self.cost_price > 0:
            margin = ((self.selling_price - self.cost_price) / self.cost_price) * 100
            return round(margin, 2)
        return 0


class ProductPurchase(models.Model):
    """Model for individual product purchases with batch management."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Shop relationship
    shop = models.ForeignKey(
        'settings.Shop',
        on_delete=models.CASCADE,
        related_name='product_purchases',
        help_text='Shop this purchase belongs to'
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='purchases',
        help_text='Related product'
    )

    # Purchase details
    purchase_date = models.DateField(help_text='Date of purchase')
    batch_number = models.CharField(
        max_length=50,
        blank=True,
        help_text='Batch/Lot number'
    )

    # Pricing per unit for this purchase
    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Purchase price per unit'
    )
    selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Selling price per unit'
    )

    # Quantity management
    quantity = models.PositiveIntegerField(help_text='Total quantity purchased')
    remaining_quantity = models.PositiveIntegerField(
        default=0,
        help_text='Remaining quantity available for sale'
    )

    # Supplier information
    supplier = models.ForeignKey(
        'Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Supplier for this purchase'
    )

    # Expiry for perishable items
    expiry_date = models.DateField(
        null=True,
        blank=True,
        help_text='Expiry date (for perishable items)'
    )

    # Staff handling
    handled_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        help_text='Staff member who handled the purchase'
    )

    # Notes
    notes = models.TextField(blank=True, help_text='Purchase notes')

    # Status
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-purchase_date', '-created_at']
        unique_together = ['product', 'batch_number']  # Optional, if batch numbers should be unique per product

    def __str__(self):
        return f"{self.product.name} - Batch {self.batch_number or self.id} ({self.purchase_date})"

    def save(self, *args, **kwargs):
        """Set remaining quantity on creation."""
        if not self.pk:  # New instance
            self.remaining_quantity = self.quantity
        super().save(*args, **kwargs)

    def get_profit_margin(self):
        """Calculate profit margin for this purchase."""
        if self.purchase_price > 0:
            margin = ((self.selling_price - self.purchase_price) / self.purchase_price) * 100
            return round(margin, 2)
        return 0
    
    def adjust_stock(self, quantity_change, reason=""):
        """Safely adjust stock quantity with validation."""
        new_quantity = self.remaining_quantity + quantity_change
        
        # Prevent negative stock
        if new_quantity < 0:
            raise ValueError(f"Insufficient stock. Cannot reduce {abs(quantity_change)} units from batch {self.batch_number or self.id}. Only {self.remaining_quantity} units available.")
        
        # Update remaining quantity
        self.remaining_quantity = new_quantity
        self.save(update_fields=['remaining_quantity'])


class Supplier(models.Model):
    """Model for computer suppliers."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    PAYMENT_TERMS_CHOICES = [
        ('cash', 'Cash on Delivery'),
        ('credit_15', '15 Days Credit'),
        ('credit_30', '30 Days Credit'),
        ('credit_45', '45 Days Credit'),
        ('advance', 'Advance Payment'),
    ]

    # Shop relationship
    shop = models.ForeignKey(
        'settings.Shop',
        on_delete=models.CASCADE,
        related_name='suppliers',
        help_text='Shop this supplier belongs to'
    )

    name = models.CharField(max_length=100, help_text='Supplier name')
    contact_person = models.CharField(max_length=100, blank=True, help_text='Contact person name')
    phone = models.CharField(max_length=15, help_text='Phone number')
    email = models.EmailField(blank=True, help_text='Email address')
    address = models.TextField(blank=True, help_text='Business address')

    # Business details
    tax_number = models.CharField(max_length=50, blank=True, help_text='NTN/STRN number')
    payment_terms = models.CharField(
        max_length=20,
        choices=PAYMENT_TERMS_CHOICES,
        default='cash',
        help_text='Payment terms'
    )

    # Supplier rating
    rating = models.PositiveIntegerField(
        default=5,
        help_text='Supplier rating (1-5)'
    )

    # Status
    is_active = models.BooleanField(default=True, help_text='Is supplier active?')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ComputerRepair(models.Model):
    """Model for computer repair services."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    REPAIR_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('waiting_parts', 'Waiting for Parts'),
        ('ready', 'Ready for Pickup'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    # Shop relationship
    shop = models.ForeignKey(
        'settings.Shop',
        on_delete=models.CASCADE,
        related_name='computer_repairs',
        help_text='Shop this repair belongs to'
    )

    customer_name = models.CharField(max_length=100, help_text='Customer name')
    customer_phone = models.CharField(max_length=15, help_text='Customer phone')
    customer_email = models.EmailField(blank=True, help_text='Customer email')

    # Device details
    brand = models.CharField(max_length=100, help_text='Computer brand')
    model = models.CharField(max_length=100, help_text='Computer model')
    serial_number = models.CharField(max_length=50, blank=True, help_text='Serial number')
    color = models.CharField(max_length=50, blank=True, help_text='Computer color')

    # Repair details
    problem_description = models.TextField(help_text='Problem description')
    repair_type = models.CharField(
        max_length=50,
        help_text='Type of repair (screen, battery, etc.)'
    )

    # Pricing
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Estimated repair cost'
    )
    actual_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Actual repair cost'
    )
    advance_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Advance payment'
    )

    # Status and dates
    status = models.CharField(
        max_length=20,
        choices=REPAIR_STATUS_CHOICES,
        default='pending',
        help_text='Repair status'
    )
    received_date = models.DateTimeField(auto_now_add=True, help_text='Date received')
    estimated_completion_date = models.DateField(null=True, blank=True, help_text='Estimated completion date')
    actual_completion_date = models.DateField(null=True, blank=True, help_text='Actual completion date')
    delivered_date = models.DateField(null=True, blank=True, help_text='Date delivered')

    # Technician
    assigned_technician = models.CharField(max_length=100, blank=True, help_text='Assigned technician')

    # Notes
    repair_notes = models.TextField(blank=True, help_text='Internal repair notes')
    customer_notes = models.TextField(blank=True, help_text='Notes for customer')

    # Warranty
    under_warranty = models.BooleanField(default=False, help_text='Is repair under warranty?')
    warranty_period = models.PositiveIntegerField(
        default=30,
        help_text='Warranty period in days'
    )

    class Meta:
        ordering = ['-received_date']

    def __str__(self):
        return f"Repair - {self.customer_name} - {self.brand} {self.model}"




class ComputerBrand(models.Model):
    """Model for computer device brands."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Shop relationship
    shop = models.ForeignKey(
        'settings.Shop',
        on_delete=models.CASCADE,
        related_name='computer_brands',
        help_text='Shop this brand belongs to'
    )

    name = models.CharField(max_length=100, help_text='Brand name (e.g., Dell, HP, Apple)')
    is_active = models.BooleanField(default=True, help_text='Is brand active?')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = ['shop', 'name']

    def __str__(self):
        return self.name


class ComputerModel(models.Model):
    """Model for computer device models."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Shop relationship
    shop = models.ForeignKey(
        'settings.Shop',
        on_delete=models.CASCADE,
        related_name='computer_models',
        help_text='Shop this model belongs to'
    )

    brand = models.ForeignKey(
        ComputerBrand,
        on_delete=models.CASCADE,
        related_name='models',
        help_text='Related brand'
    )
    name = models.CharField(max_length=100, help_text='Model name (e.g., XPS 15, MacBook Pro)')
    is_active = models.BooleanField(default=True, help_text='Is model active?')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['brand', 'name']
        unique_together = ['shop', 'brand', 'name']

    def __str__(self):
        return f"{self.brand.name} {self.name}"


class ComputerPurchase(models.Model):
    """Model for individual computer purchases from customers."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    COMPUTER_TYPE_CHOICES = [
        ('desktop', 'Desktop'),
        ('laptop', 'Laptop'),
        ('tablet', 'Tablet'),
        ('all_in_one', 'All-in-One'),
        ('workstation', 'Workstation'),
    ]

    # Shop relationship
    shop = models.ForeignKey(
        'settings.Shop',
        on_delete=models.CASCADE,
        related_name='computer_purchases',
        help_text='Shop this purchase belongs to'
    )

    # Customer information
    customer_name = models.CharField(max_length=100, help_text='Customer name')
    customer_phone = models.CharField(max_length=15, help_text='Customer phone')
    customer_email = models.EmailField(blank=True, help_text='Customer email')
    id_card_number = models.CharField(max_length=20, blank=True, help_text='Customer ID card number')

    # Link to customer account if exists
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Linked customer account'
    )

    # Device details
    brand = models.ForeignKey(
        ComputerBrand,
        on_delete=models.CASCADE,
        help_text='Computer brand'
    )
    model = models.ForeignKey(
        ComputerModel,
        on_delete=models.CASCADE,
        help_text='Computer model'
    )
    color = models.CharField(max_length=50, blank=True, null=True, help_text='Computer color')
    serial_number = models.CharField(max_length=50, help_text='Serial number')
    asset_tag = models.CharField(max_length=50, blank=True, help_text='Asset tag number')

    # Computer type
    computer_type = models.CharField(
        max_length=15,
        choices=COMPUTER_TYPE_CHOICES,
        default='laptop',
        help_text='Computer type'
    )

    # Computer specifications
    ram = models.CharField(max_length=20, blank=True, help_text='RAM (e.g., 16GB DDR4)')
    storage = models.CharField(max_length=30, blank=True, help_text='Storage (e.g., 512GB SSD)')
    storage_type = models.CharField(max_length=20, blank=True, help_text='Storage type (SSD/HDD)')
    display_size = models.CharField(max_length=20, blank=True, help_text='Display size (e.g., 15.6 inch)')
    graphics = models.CharField(max_length=50, blank=True, help_text='Graphics card')
    processor = models.CharField(max_length=50, blank=True, help_text='Processor (e.g., Intel i7, AMD Ryzen)')
    operating_system = models.CharField(max_length=30, blank=True, help_text='Operating system')

    # Device condition
    physical_condition = models.TextField(blank=True, help_text='Physical condition description')
    functional_condition = models.TextField(blank=True, help_text='Functional condition description')
    grade = models.CharField(
        max_length=10,
        choices=[
            ('a', 'Grade A (Excellent)'),
            ('b', 'Grade B (Good)'),
            ('c', 'Grade C (Fair)'),
            ('d', 'Grade D (Poor)'),
        ],
        help_text='Device condition grade'
    )

    # Accessories included
    box_packed = models.BooleanField(default=False, help_text='Comes with original box?')
    accessories_included = models.TextField(blank=True, help_text='Included accessories')

    # Pricing
    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Purchase price'
    )

    # Purchase details
    purchase_date = models.DateField(auto_now_add=True, help_text='Date of purchase')

    # Staff handling
    handled_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        help_text='Staff member who handled the purchase'
    )

    # Notes
    notes = models.TextField(blank=True, help_text='Purchase notes')

    # Device photos
    front_photo = models.ImageField(
        upload_to=computer_purchase_photo_path,
        storage=R2MediaStorage(),
        blank=True,
        null=True,
        help_text='Front view photo'
    )
    back_photo = models.ImageField(
        upload_to=computer_purchase_photo_path,
        storage=R2MediaStorage(),
        blank=True,
        null=True,
        help_text='Back view photo'
    )

    # ID card photos
    id_card_front = models.ImageField(
        upload_to=computer_purchase_photo_path,
        storage=R2MediaStorage(),
        blank=True,
        null=True,
        help_text='ID card front photo'
    )
    id_card_back = models.ImageField(
        upload_to=computer_purchase_photo_path,
        storage=R2MediaStorage(),
        blank=True,
        null=True,
        help_text='ID card back photo'
    )

    # Warranty Status
    WARRANTY_STATUS_CHOICES = [
        ('manufacturer', 'Manufacturer Warranty'),
        ('extended', 'Extended Warranty'),
        ('no_warranty', 'No Warranty'),
        ('expired', 'Expired Warranty'),
    ]

    warranty_status = models.CharField(
        max_length=20,
        choices=WARRANTY_STATUS_CHOICES,
        blank=True,
        help_text='Warranty status'
    )
    warranty_expiry = models.DateField(null=True, blank=True, help_text='Warranty expiry date')

    # Status
    sold = models.BooleanField(default=False, help_text='Is computer sold?')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-purchase_date']

    def __str__(self):
        return f"{self.customer_name} - {self.brand.name} {self.model.name} ({self.color or 'N/A'})"


class ComputerImage(models.Model):
    """Model for computer device images with main image support."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Shop relationship
    shop = models.ForeignKey(
        'settings.Shop',
        on_delete=models.CASCADE,
        related_name='computer_images',
        help_text='Shop this image belongs to'
    )
    
    # Computer purchase relationship
    computer_purchase = models.ForeignKey(
        ComputerPurchase,
        on_delete=models.CASCADE,
        related_name='images',
        help_text='Computer purchase this image belongs to'
    )
    
    # Image details
    image = models.ImageField(
        upload_to=computer_image_path,
        storage=R2MediaStorage(),
        help_text='Computer device image'
    )
    is_main = models.BooleanField(
        default=False,
        help_text='Is this the main image?'
    )
    caption = models.CharField(
        max_length=100,
        blank=True,
        help_text='Image caption or description'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_main', 'created_at']
        
    def __str__(self):
        return f"Image for {self.computer_purchase} - {'Main' if self.is_main else 'Secondary'}"