from rest_framework import serializers
from django.db import IntegrityError
from .models import Customer, CustomerTransaction, CustomerDueReport

# Serializer for Customer model
# Fields included: Core customer details for lists/details (id, name, phone, email, address, current_balance, customer_type, is_active); computed balance_display for UI formatting and balance_status for filtering - excludes stats fields as they can be computed from transactions if needed.
class CustomerSerializer(serializers.ModelSerializer):
    balance_display = serializers.ReadOnlyField()
    balance_status = serializers.ReadOnlyField()
    
    class Meta:
        model = Customer
        fields = ['id', 'shop', 'name', 'phone', 'email', 'address', 'current_balance', 'customer_type', 'is_active', 'balance_display', 'balance_status', 'total_purchases', 'profile_image']
        read_only_fields = ['shop']

    def create(self, validated_data):
        """Set shop from request user and handle unique constraint errors."""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'shop') and request.user.shop:
            validated_data['shop'] = request.user.shop
            validated_data['is_active'] = True

        try:
            return super().create(validated_data)
        except IntegrityError as e:
            if 'UNIQUE constraint failed: customers_customer.shop_id, customers_customer.phone' in str(e):
                raise serializers.ValidationError({
                    'phone': ['A customer with this phone number already exists.']
                })
            raise

# Serializer for CustomerTransaction model
# Fields included: Transaction essentials for ledger display (id, transaction_type, amount, balance_after, description, transaction_date); related customer_name_display and recorded_by_name_display for context without full objects - excludes balance_before as balance_after suffices for display.
class CustomerTransactionSerializer(serializers.ModelSerializer):
    customer_name_display = serializers.CharField(source='customer.name', read_only=True)
    recorded_by_name_display = serializers.SerializerMethodField()
    sale_id = serializers.UUIDField(source='sale.id', read_only=True, allow_null=True)

    class Meta:
        model = CustomerTransaction
        fields = ['id', 'shop', 'transaction_type', 'amount', 'balance_after', 'description', 'transaction_date', 'customer_name_display', 'recorded_by_name_display', 'sale_id']
        read_only_fields = ['shop']

    def create(self, validated_data):
        """Set shop from request user."""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'shop') and request.user.shop:
            validated_data['shop'] = request.user.shop
        return super().create(validated_data)

    def get_recorded_by_name_display(self, obj):
        return obj.recorded_by.get_full_name() if obj.recorded_by else None

# Serializer for CustomerDueReport model
# Fields included: Report data for due tracking (id, report_date, total_outstanding, days_overdue, last_payment_date, last_purchase_date); related customer_name_display and customer_phone_display for identification - excludes created_at as report_date suffices.
class CustomerDueReportSerializer(serializers.ModelSerializer):
    customer_name_display = serializers.CharField(source='customer.name', read_only=True)
    customer_phone_display = serializers.CharField(source='customer.phone', read_only=True)

    class Meta:
        model = CustomerDueReport
        fields = ['id', 'shop', 'report_date', 'total_outstanding', 'days_overdue', 'last_payment_date', 'last_purchase_date', 'customer_name_display', 'customer_phone_display']
        read_only_fields = ['shop']

    def create(self, validated_data):
        """Set shop from request user."""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'shop') and request.user.shop:
            validated_data['shop'] = request.user.shop
        return super().create(validated_data)

# Serializer for Customer Ledger (customer with transaction history)
class CustomerLedgerSerializer(serializers.ModelSerializer):
    transactions = CustomerTransactionSerializer(many=True, read_only=True)
    balance_display = serializers.ReadOnlyField()
    balance_status = serializers.ReadOnlyField()

    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone', 'email', 'address', 'current_balance', 'customer_type', 'balance_display', 'balance_status', 'transactions']

# Serializer for Outstanding Customers
class OutstandingCustomersSerializer(serializers.ModelSerializer):
    balance_display = serializers.ReadOnlyField()
    balance_status = serializers.ReadOnlyField()

    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone', 'email', 'current_balance', 'balance_display', 'balance_status', 'total_purchases', 'customer_type']

# Serializer for Creating Customer Transactions
class CustomerCreateTransactionSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField()
    transaction_type = serializers.ChoiceField(choices=[('debit', 'Debit'), ('credit', 'Credit')])
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    description = serializers.CharField(max_length=255)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def create(self, validated_data):
        """Create transaction with shop from request context."""
        request = self.context.get('request')
        customer = Customer.objects.get(id=validated_data['customer_id'])
        
        # Create transaction with shop
        transaction = CustomerTransaction.objects.create(
            customer=customer,
            transaction_type=validated_data['transaction_type'],
            amount=validated_data['amount'],
            description=validated_data['description'],
            notes=validated_data.get('notes', ''),
            recorded_by=request.user if request and request.user else None,
            shop=request.user.shop if request and request.user and hasattr(request.user, 'shop') else None
        )
        
        return transaction
