from rest_framework import serializers
from django.db import transaction
from decimal import Decimal, InvalidOperation
from .models import Sale, SaleItem, SalePayment
from settings.models import Shop

# Serializer for Sale model
# Fields included: Sale summary for transaction history (id, sale_number, sale_date, customer_name, customer_phone, subtotal, discount_amount, tax_amount, total_amount, payment_method, amount_paid, change_amount, total_profit, is_completed, is_cancelled, notes); related sold_by_name_display, customer_name_display for context; computed profit_margin for performance tracking - excludes receipt fields as not primary.
class SaleSerializer(serializers.ModelSerializer):
    sold_by_name_display = serializers.SerializerMethodField()
    customer_name_display = serializers.SerializerMethodField()
    profit_margin = serializers.ReadOnlyField()
    sale_items = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = ['id', 'shop', 'sale_number', 'sale_date', 'customer_name', 'customer_phone', 'subtotal', 'discount_amount', 'tax_amount', 'total_amount', 'payment_method', 'amount_paid', 'change_amount', 'total_profit', 'is_completed', 'is_cancelled', 'notes', 'sold_by_name_display', 'customer_name_display', 'profit_margin', 'sale_items']
        read_only_fields = ['shop']

    def create(self, validated_data):
        """Set shop from request user."""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'shop') and request.user.shop:
            validated_data['shop'] = request.user.shop
        return super().create(validated_data)

    def get_sold_by_name_display(self, obj):
        return obj.sold_by.get_full_name() if obj.sold_by else None

    def get_customer_name_display(self, obj):
        return obj.customer.name if obj.customer else obj.customer_name

    def get_sale_items(self, obj):
        """Get sale items with detailed information."""
        items = obj.sale_items.all()
        return SaleItemSerializer(items, many=True).data

# Serializer for SaleItem model
# Fields included: Item details for sale breakdown (id, product_name, unit_price, quantity, total_price, cost_price, profit); related product_item_code_display, product_purchase_batch_display for context - excludes sale ID as context is from parent.
class SaleItemSerializer(serializers.ModelSerializer):
    product_item_code_display = serializers.SerializerMethodField()
    product_purchase_batch_display = serializers.SerializerMethodField()
    mobile_purchase_display = serializers.SerializerMethodField()

    class Meta:
        model = SaleItem
        fields = ['id', 'shop', 'sale', 'product', 'product_purchase', 'mobile_purchase', 'product_name', 'product_item_code', 'unit_price', 'quantity', 'total_price', 'cost_price', 'profit', 'product_item_code_display', 'product_purchase_batch_display', 'mobile_purchase_display']
        read_only_fields = ['shop']

    def create(self, validated_data):
        """Set shop from request user."""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'shop') and request.user.shop:
            validated_data['shop'] = request.user.shop
        return super().create(validated_data)

    def get_product_item_code_display(self, obj):
        return obj.product.item_code if obj.product else None

    def get_product_purchase_batch_display(self, obj):
        if obj.product_purchase:
            return f"Batch {obj.product_purchase.batch_number or obj.product_purchase.id} ({obj.product_purchase.purchase_date})"
        return None

    def get_mobile_purchase_display(self, obj):
        if obj.mobile_purchase:
            return f"IMEI: {obj.mobile_purchase.imei_number}"
        return None

# Serializer for SalePayment model
# Fields included: Payment record basics (id, amount_paid, payment_date, payment_method, notes); related received_by_name_display for context - excludes sale ID as context is from parent.
class SalePaymentSerializer(serializers.ModelSerializer):
    received_by_name_display = serializers.SerializerMethodField()

    class Meta:
        model = SalePayment
        fields = ['id', 'shop', 'amount_paid', 'payment_date', 'payment_method', 'notes', 'received_by_name_display']
        read_only_fields = ['shop']

    def create(self, validated_data):
        """Set shop from request user."""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'shop') and request.user.shop:
            validated_data['shop'] = request.user.shop
        return super().create(validated_data)

    def get_received_by_name_display(self, obj):
        return obj.received_by.get_full_name() if obj.received_by else None

# Serializer for POS sale creation (input validation only)
class POSSaleCreateSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    customer_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    customer_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    items = serializers.ListField(child=serializers.DictField(), required=True)
    # Items should include: product_id, product_name, product_item_code, unit_price, quantity, discount_amount (optional)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)
    # tax_amount is now calculated based on settings, not sent from frontend
    payment_method = serializers.ChoiceField(choices=Sale.PAYMENT_METHOD_CHOICES, required=True)
    amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    complete_sale = serializers.BooleanField(default=True, required=False)  # New field to control completion

    def validate_customer_id(self, value):
        if value:
            try:
                from customers.models import Customer
                Customer.objects.get(id=value)
            except Customer.DoesNotExist:
                raise serializers.ValidationError("Customer not found")
        return value

    def validate_amount_paid(self, value):
        if value < 0:
            raise serializers.ValidationError("Amount paid cannot be negative")
        return value

    def create(self, validated_data):
        from django.utils import timezone
        from decimal import Decimal
        from .models import Sale, SaleItem

        # Extract data
        customer_id = validated_data.get('customer_id')
        customer_name = validated_data.get('customer_name', '')
        customer_phone = validated_data.get('customer_phone', '')
        items = validated_data['items']
        discount_amount = validated_data['discount_amount']
        payment_method = validated_data['payment_method']
        amount_paid = validated_data['amount_paid']
        notes = validated_data.get('notes', '')
        complete_sale = validated_data.get('complete_sale', True)

        # Calculate totals (ensure all values are Decimal)
        subtotal = sum(Decimal(str(item['unit_price'])) * Decimal(str(item['quantity'])) for item in items)

        # Get tax settings
        try:
            settings = Shop.objects.first()
            if settings and settings.tax_enabled:
                tax_amount = (subtotal - discount_amount) * (settings.tax_percentage / 100)
            else:
                tax_amount = 0
        except Shop.DoesNotExist:
            tax_amount = 0  # Default to no tax if settings don't exist

        total_amount = subtotal - discount_amount + tax_amount

        # Set default values for walk-in customers
        if not customer_name:
            customer_name = 'Walk-in Customer'
        if not customer_phone:
            customer_phone = 'N/A'

        # Get user's shop
        user_shop = None
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'shop') and request.user.shop:
            user_shop = request.user.shop

        # Create sale
        sale = Sale.objects.create(
            shop=user_shop,
            customer_id=customer_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            sold_by=self.context['request'].user,
            subtotal=subtotal,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            total_amount=total_amount,
            payment_method=payment_method,
            amount_paid=amount_paid,
            change_amount=max(0, amount_paid - total_amount),
            is_completed=complete_sale,
            notes=notes
        )

        # Create customer transaction for all sales (not just credit)
        if customer_id:
            from customers.models import CustomerTransaction
            transaction_type = 'debit' if payment_method == 'credit' else 'credit'
            CustomerTransaction.objects.create(
                shop=user_shop,
                customer_id=customer_id,
                transaction_type=transaction_type,
                amount=total_amount,
                description=f"Sale #{sale.sale_number}",
                recorded_by=self.context['request'].user,
                sale=sale
            )

        # Create sale items
        total_profit = 0
        for item in items:
            cost_price = 0
            product_purchase_id = None
            computer_purchase_id = None

            # Handle product sales - use specific batch if provided, otherwise FIFO
            # Handle computer sales - use specific computer purchase if provided
            if item.get('computer_purchase_id'):
                from inventory.models import ComputerPurchase
                computer_purchase = ComputerPurchase.objects.get(id=item['computer_purchase_id'])
                if computer_purchase.sold:
                    raise serializers.ValidationError(f"Computer {computer_purchase.serial_number} is already sold")
                
                # Mark computer as sold
                computer_purchase.sold = True
                computer_purchase.save(update_fields=['sold'])
                
                cost_price = computer_purchase.purchase_price
                product_purchase_id = None
                computer_purchase_id = computer_purchase.id
            elif item.get('product_id'):
                from inventory.models import ProductPurchase
                product_id = item['product_id']
                quantity_needed = item['quantity']

                # If specific batch is selected
                if item.get('product_purchase_id'):
                    specific_batch = ProductPurchase.objects.get(id=item['product_purchase_id'])
                    if specific_batch.remaining_quantity >= quantity_needed:
                        # Use the specific batch
                        cost_price = specific_batch.purchase_price
                        specific_batch.remaining_quantity -= quantity_needed
                        specific_batch.save()
                        product_purchase_id = specific_batch.id
                    else:
                        raise serializers.ValidationError(f"Insufficient quantity in selected batch")
                else:
                    # Use FIFO from batches
                    batches = ProductPurchase.objects.filter(
                        product_id=product_id,
                        remaining_quantity__gt=0
                    ).order_by('purchase_date')

                    total_cost = Decimal('0')
                    remaining_to_sell = quantity_needed

                    for batch in batches:
                        if remaining_to_sell <= 0:
                            break

                        # How much can we take from this batch?
                        available_from_batch = min(remaining_to_sell, batch.remaining_quantity)

                        # Calculate cost for this portion
                        batch_cost = Decimal(str(available_from_batch)) * batch.purchase_price
                        total_cost += batch_cost

                        # Reduce remaining quantity in batch
                        batch.remaining_quantity -= available_from_batch
                        batch.save()

                        # Track which batch we're using (use the first/last one for reference)
                        if not product_purchase_id:
                            product_purchase_id = batch.id

                        remaining_to_sell -= available_from_batch

                    # Calculate average cost price
                    cost_price = Decimal(str(total_cost)) / Decimal(str(quantity_needed)) if quantity_needed > 0 else Decimal('0')
            else:
                cost_price = Decimal(str(item.get('cost_price', 0)))

            # Calculate discounted unit price for profit calculation
            item_discount = Decimal(str(item.get('discount_amount', 0)))
            item_quantity = Decimal(str(item['quantity']))
            item_unit_price = Decimal(str(item['unit_price']))
            discounted_unit_price = item_unit_price - (item_discount / item_quantity) if item_quantity > 0 else item_unit_price

            sale_item = SaleItem.objects.create(
                shop=user_shop,
                sale=sale,
                product_id=item.get('product_id'),
                product_purchase_id=product_purchase_id,
                computer_purchase_id=computer_purchase_id,
                product_name=item['product_name'],
                product_item_code=item.get('product_item_code') or '',
                unit_price=discounted_unit_price,
                quantity=int(item_quantity),
                cost_price=cost_price,
                profit=(discounted_unit_price - cost_price) * item_quantity
            )
            total_profit += sale_item.profit

        # Update sale profit
        sale.total_profit = total_profit
        sale.save()

        return sale

# Serializer for sale receipt (output only)
class SaleReceiptSerializer(serializers.Serializer):
    sale_number = serializers.CharField()
    sale_date = serializers.DateTimeField()
    customer_name = serializers.CharField()
    customer_phone = serializers.CharField()
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_method = serializers.CharField()
    amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2)
    change_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    sale_items = SaleItemSerializer(many=True, read_only=True)
    shop_info = serializers.SerializerMethodField()

    def get_shop_info(self, obj):
        try:
            settings = Shop.objects.first()
            if settings:
                return {
                    'name': settings.shop_name,
                    'address': settings.address or '',
                    'phone': settings.phone or '',
                    'email': settings.email or ''
                }
        except Shop.DoesNotExist:
            pass
        # Fallback to defaults
        return {
            'name': 'Shop',
            'address': 'Your Shop Address',
            'phone': 'Your Phone Number',
            'email': ''
        }
