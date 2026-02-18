from datetime import date
from rest_framework import serializers
from .models import (
    Product, ProductPurchase, ComputerPurchase, Supplier, ComputerRepair,
    ComputerBrand, ComputerModel, Category, ComputerImage
)

# Serializer for Category model
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'shop', 'name', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'shop']

    def create(self, validated_data):
        """Set shop from request user."""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'shop') and request.user.shop:
            validated_data['shop'] = request.user.shop
        return super().create(validated_data)


# Serializer for Product model
# Fields included: Product basics for inventory management (id, name, item_code, description, category, is_active); computed fields for pricing and stock; profit_margin for pricing insights and is_low_stock for alerts - excludes min_stock_level as is_low_stock covers it.
class ProductSerializer(serializers.ModelSerializer):
    profit_margin = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()
    stock_quantity = serializers.ReadOnlyField()
    cost_price = serializers.ReadOnlyField()
    selling_price = serializers.ReadOnlyField()
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'shop', 'name', 'item_code', 'description', 'cost_price', 'selling_price', 'stock_quantity', 'category', 'category_name', 'is_active', 'profit_margin', 'is_low_stock', 'min_stock_level']
        read_only_fields = ['shop']

    def create(self, validated_data):
        """Set shop from request user."""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'shop') and request.user.shop:
            validated_data['shop'] = request.user.shop
        return super().create(validated_data)


# Serializer for ProductPurchase model
class ProductPurchaseSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    profit_margin = serializers.ReadOnlyField()

    class Meta:
        model = ProductPurchase
        fields = [
            'id', 'shop', 'product', 'product_name', 'purchase_date', 'batch_number',
            'purchase_price', 'selling_price', 'quantity', 'remaining_quantity',
            'supplier', 'supplier_name', 'handled_by', 'notes',
            'profit_margin', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'remaining_quantity', 'shop']

    def create(self, validated_data):
        """Set shop from request user."""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'shop') and request.user.shop:
            validated_data['shop'] = request.user.shop
        return super().create(validated_data)


# Serializer for ComputerPurchase model
class ComputerPurchaseSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    model_name = serializers.CharField(source='model.name', read_only=True)
    images = serializers.SerializerMethodField()
    main_image = serializers.SerializerMethodField()

    class Meta:
        model = ComputerPurchase
        fields = [
            'id', 'shop', 'customer_name', 'customer_phone', 'customer_email', 'id_card_number',
            'customer', 'brand', 'brand_name', 'model', 'model_name', 'color',
            'serial_number', 'asset_tag', 'computer_type', 'ram', 'storage', 'storage_type',
            'display_size', 'graphics', 'processor', 'operating_system', 'physical_condition',
            'functional_condition', 'grade', 'box_packed', 'accessories_included',
            'purchase_price', 'purchase_date', 'handled_by', 'notes',
            'front_photo', 'back_photo', 'id_card_front', 'id_card_back',
            'warranty_status', 'warranty_expiry', 'sold', 'created_at', 'updated_at', 'images', 'main_image'
        ]
        read_only_fields = ['created_at', 'updated_at', 'shop']

    def get_images(self, obj):
        """Get all computer images."""
        images = obj.images.all()
        return ComputerImageSerializer(images, many=True, context=self.context).data
    
    def get_main_image(self, obj):
        """Get the main image or first image as fallback."""
        main_image = obj.images.filter(is_main=True).first()
        if not main_image:
            main_image = obj.images.first()
        if main_image:
            return ComputerImageSerializer(main_image, context=self.context).data
        return None

    def create(self, validated_data):
        """Set shop from request user."""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'shop') and request.user.shop:
            validated_data['shop'] = request.user.shop
        return super().create(validated_data)


# Serializer for ComputerImage model
class ComputerImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ComputerImage
        fields = ['id', 'shop', 'computer_purchase', 'image', 'image_url', 'is_main', 'caption', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'shop']

    def get_image_url(self, obj):
        """Get full URL for the image."""
        request = self.context.get('request')
        if obj.image and hasattr(obj.image, 'url'):
            image_url = obj.image.url
            if request:
                return request.build_absolute_uri(image_url)
            return image_url
        return None

    def create(self, validated_data):
        """Set shop from request user and handle main image logic."""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'shop') and request.user.shop:
            validated_data['shop'] = request.user.shop
        
        # If this is set as main image, unset other main images for this mobile
        if validated_data.get('is_main', False):
            mobile_purchase = validated_data.get('mobile_purchase')
            if mobile_purchase:
                MobileImage.objects.filter(mobile_purchase=mobile_purchase, is_main=True).update(is_main=False)
        
        return super().create(validated_data)

# Serializer for Supplier model
# Fields included: Supplier info for purchase tracking (id, name, contact_person, phone, email, address, payment_terms, rating, is_active) - all core fields needed for supplier management.
class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['id', 'shop', 'name', 'contact_person', 'phone', 'email', 'address', 'payment_terms', 'rating', 'is_active']
        read_only_fields = ['shop']

    def create(self, validated_data):
        """Set shop from request user."""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'shop') and request.user.shop:
            validated_data['shop'] = request.user.shop
        return super().create(validated_data)

# Serializer for ComputerRepair model
# Fields included: Repair details for service tracking (id, customer_name, customer_phone, brand, model, problem_description, repair_type, estimated_cost, actual_cost, advance_paid, status, received_date, estimated_completion_date, assigned_technician, under_warranty, notes) - all fields essential for repair workflow.
class ComputerRepairSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComputerRepair
        fields = ['id', 'shop', 'customer_name', 'customer_phone', 'customer_email', 'brand', 'model', 'serial_number', 'color', 'problem_description', 'repair_type', 'estimated_cost', 'actual_cost', 'advance_paid', 'status', 'received_date', 'estimated_completion_date', 'actual_completion_date', 'delivered_date', 'assigned_technician', 'repair_notes', 'customer_notes', 'under_warranty', 'warranty_period']
        read_only_fields = ['shop']

    def create(self, validated_data):
        """Set shop from request user."""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'shop') and request.user.shop:
            validated_data['shop'] = request.user.shop
        return super().create(validated_data)

# Serializer for ComputerBrand model
# Fields included: Brand basics (id, name, is_active) - minimal for brand management.
class ComputerBrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComputerBrand
        fields = ['id', 'shop', 'name', 'is_active']
        read_only_fields = ['shop']

    def create(self, validated_data):
        """Set shop from request user."""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'shop') and request.user.shop:
            validated_data['shop'] = request.user.shop
        return super().create(validated_data)

# Serializer for ComputerModel model
# Fields included: Model basics (id, name, is_active); related brand_name_display for context - excludes brand ID as display suffices.
class ComputerModelSerializer(serializers.ModelSerializer):
    brand_name_display = serializers.CharField(source='brand.name', read_only=True)

    class Meta:
        model = ComputerModel
        fields = ['id', 'shop', 'brand', 'name', 'is_active', 'brand_name_display']
        read_only_fields = ['shop']

    def create(self, validated_data):
        """Set shop from request user."""
        request = self.context.get('request')
        if request and request.user and hasattr(request.user, 'shop') and request.user.shop:
            validated_data['shop'] = request.user.shop
        return super().create(validated_data)


# Serializer for stock update operations
# Fields included: operation (add/subtract), quantity - for updating product stock levels.
class StockUpdateSerializer(serializers.Serializer):
    operation = serializers.ChoiceField(choices=['add', 'subtract'])
    quantity = serializers.IntegerField(min_value=1)

# Serializer for computer stock update operations
# Fields included: operation (sell/restock), quantity, serial numbers - for managing computer inventory with serial number tracking.
class ComputerStockUpdateSerializer(serializers.Serializer):
    operation = serializers.ChoiceField(choices=['sell', 'restock'])
    quantity = serializers.IntegerField(min_value=1)
    serial_numbers = serializers.ListField(
        child=serializers.CharField(max_length=20),
        required=False,
        allow_empty=True
    )
