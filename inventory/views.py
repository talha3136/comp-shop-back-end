from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum, Count, F, Subquery, OuterRef, Max, Value
from django.db.models.functions import Coalesce
from django.db import models
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import (
    Product, ProductPurchase, ComputerPurchase, Supplier, ComputerRepair,
    ComputerBrand, ComputerModel, Category, ComputerImage
)
from .serializers import (
    ProductSerializer, ProductPurchaseSerializer, ComputerPurchaseSerializer,
    SupplierSerializer, ComputerRepairSerializer,
    ComputerBrandSerializer, ComputerModelSerializer, CategorySerializer,
    StockUpdateSerializer, ComputerStockUpdateSerializer, ComputerImageSerializer
)
from accounts.permissions import IsStaffUser

class CategoryViewSet(viewsets.ModelViewSet):
    """Category management viewset with CRUD operations."""
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        queryset = Category.objects.filter(is_active=True)
        # Filter by user's shop unless super admin
        if not self.request.user.is_super_admin():
            queryset = queryset.filter(shop=self.request.user.shop)
        return queryset

    def perform_destroy(self, instance):
        """Soft delete by setting is_active to False."""
        instance.is_active = False
        instance.save()

class ProductViewSet(viewsets.ModelViewSet):
    """Product management viewset with CRUD operations and custom actions."""
    queryset = Product.objects.filter(is_active=True)
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]
    pagination_class = PageNumberPagination

    def get_serializer_class(self):
        return ProductSerializer

    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True)

        # Filter by user's shop unless super admin
        if not self.request.user.is_super_admin():
            queryset = queryset.filter(shop=self.request.user.shop)

        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__name__icontains=category)


        # Filter by low stock
        low_stock = self.request.query_params.get('low_stock')
        if low_stock == 'true':
            queryset = queryset.annotate(
                total_stock=Coalesce(Sum('purchases__remaining_quantity'), Value(0))
            ).filter(total_stock__lte=F('min_stock_level'))

        # Search by name or item code
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(item_code__icontains=search)
            )

        return queryset.order_by('name')


    @action(detail=True, methods=['post'], url_path='update-product-stock')
    @swagger_auto_schema(
        operation_description="Update product stock",
        request_body=StockUpdateSerializer,
        responses={200: 'Stock updated successfully', 400: 'Bad request'}
    )
    def update_product_stock(self, request, pk=None):
        """Update product stock."""
        product_id = pk
        product = get_object_or_404(Product, id=product_id)
        serializer = StockUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if serializer.validated_data['operation'] == 'add':
            product.stock_quantity += serializer.validated_data['quantity']
        elif serializer.validated_data['operation'] == 'subtract':
            if product.stock_quantity < serializer.validated_data['quantity']:
                return Response(
                    {'error': 'Insufficient stock'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            product.stock_quantity -= serializer.validated_data['quantity']

        product.save()

        return Response({
            'message': 'Stock updated successfully',
            'new_quantity': product.stock_quantity
        })

    @action(detail=False, methods=['get'], url_path='low-stock-products')
    @swagger_auto_schema(
        operation_description="List products with low stock",
        responses={200: ProductSerializer(many=True)}
    )
    def low_stock_products(self, request):
        """List products with low stock."""
        queryset = Product.objects.filter(is_active=True).annotate(
            total_stock=Coalesce(Sum('purchases__remaining_quantity'), Value(0))
        ).filter(total_stock__lte=F('min_stock_level')).order_by('total_stock')

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='pos-product-search')
    @swagger_auto_schema(
        operation_description="Search products for POS with latest selling price and stock info",
        manual_parameters=[
            openapi.Parameter('q', openapi.IN_QUERY, description="Search query", type=openapi.TYPE_STRING)
        ],
        responses={200: 'POS search results'}
    )
    def pos_product_search(self, request):
        """Search products for POS with latest selling price and stock info."""
        search_query = request.query_params.get('q', '').strip()

        if not search_query:
            return Response({
                'results': [],
                'count': 0
            })

        # Get latest selling price from product purchases
        latest_purchase_subquery = ProductPurchase.objects.filter(
            product=OuterRef('pk'),
            remaining_quantity__gt=0
        ).order_by('-purchase_date').values('selling_price')[:1]

        # Get products with search and latest price
        products = Product.objects.filter(
            Q(name__icontains=search_query) |
            Q(item_code__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(category__name__icontains=search_query),
            is_active=True
        ).annotate(
            latest_selling_price=Coalesce(Subquery(latest_purchase_subquery), Value(0), output_field=models.DecimalField(max_digits=10, decimal_places=2)),
            total_stock=Coalesce(Sum('purchases__remaining_quantity'), Value(0))
        ).values(
            'id', 'name', 'item_code', 'category', 'description',
            'latest_selling_price', 'total_stock', 'min_stock_level'
        ).order_by('name')[:20]  # Limit to 20 results for POS performance

        # Format results for POS
        results = []
        for product in products:
            results.append({
                'id': product['id'],
                'name': product['name'],
                'type': 'Product',
                'price': float(product['latest_selling_price']),
                'stock': int(product['total_stock']),
                'item_code': product['item_code'] or '',
                'category': product['category'] or '',
                'product_id': product['id'],
                'mobile_purchase_id': None,
                'low_stock': product['total_stock'] <= product['min_stock_level']
            })

        return Response({
            'results': results,
            'count': len(results)
        })

    @action(detail=False, methods=['get'], url_path='company/(?P<company_id>[0-9]+)')
    def company_products(self, request, company_id=None):
        """Get products for a specific company/shop."""
        try:
            # Validate that the company/shop exists
            from settings.models import Shop
            shop = Shop.objects.get(id=company_id)

            # Filter products by the specified company/shop
            queryset = Product.objects.filter(is_active=True, shop_id=company_id)

            # Apply the same filtering logic as get_queryset
            category = self.request.query_params.get('category')
            if category:
                queryset = queryset.filter(category__name__icontains=category)


            low_stock = self.request.query_params.get('low_stock')
            if low_stock == 'true':
                queryset = queryset.annotate(
                    total_stock=Coalesce(Sum('purchases__remaining_quantity'), Value(0))
                ).filter(total_stock__lte=F('min_stock_level'))

            search = self.request.query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) | Q(item_code__icontains=search)
                )

            # Apply pagination
            page = self.paginate_queryset(queryset.order_by('name'))
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            # If no pagination, return all results
            serializer = self.get_serializer(queryset.order_by('name'), many=True)
            return Response(serializer.data)

        except Shop.DoesNotExist:
            return Response(
                {'error': 'Company not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductPurchaseViewSet(viewsets.ModelViewSet):
    """Product purchase management viewset with batch tracking."""
    queryset = ProductPurchase.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]

    def get_serializer_class(self):
        return ProductPurchaseSerializer

    def get_queryset(self):
        queryset = ProductPurchase.objects.all().select_related('product', 'supplier', 'handled_by')

        # Filter by user's shop unless super admin
        if not self.request.user.is_super_admin():
            queryset = queryset.filter(shop=self.request.user.shop)

        # Filter by product
        product_id = self.request.query_params.get('product_id')
        if product_id:
            queryset = queryset.filter(product_id=product_id)

        # Filter by supplier
        supplier_id = self.request.query_params.get('supplier_id')
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)

        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(purchase_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(purchase_date__lte=end_date)

        # Search by batch number or notes
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(batch_number__icontains=search) |
                Q(notes__icontains=search) |
                Q(product__name__icontains=search)
            )

        return queryset.order_by('-purchase_date')

    @action(detail=False, methods=['get'], url_path='product-purchase-summary')
    @swagger_auto_schema(
        operation_description="Get product purchase summary statistics",
        responses={200: 'Purchase summary statistics'}
    )
    def product_purchase_summary(self, request):
        """Get product purchase summary statistics."""
        total_purchases = ProductPurchase.objects.all().count()
        total_value = ProductPurchase.objects.all().aggregate(
            total=Sum('purchase_price')
        )['total'] or 0

        # Monthly purchases (current year)
        from django.db.models.functions import TruncMonth
        monthly_stats = ProductPurchase.objects.filter(
            purchase_date__year=models.functions.Now().year
        ).annotate(
            month=TruncMonth('purchase_date')
        ).values('month').annotate(
            count=Count('id'),
            total_value=Sum('purchase_price')
        ).order_by('month')

        return Response({
            'total_purchases': total_purchases,
            'total_value': total_value,
            'monthly_stats': monthly_stats
        })

    @action(detail=False, methods=['get'], url_path='product-batches')
    @swagger_auto_schema(
        operation_description="Get available batches for a product (minimal fields for POS)",
        manual_parameters=[
            openapi.Parameter('product_id', openapi.IN_QUERY, description="Product ID", type=openapi.TYPE_INTEGER, required=True)
        ],
        responses={200: 'Product batches', 400: 'Bad request'}
    )
    def product_batches(self, request):
        """Get available batches for a product (minimal fields for POS)."""
        product_id = request.query_params.get('product_id')
        if not product_id:
            return Response({'error': 'product_id required'}, status=400)

        batches = ProductPurchase.objects.filter(
            product_id=product_id,
            remaining_quantity__gt=0
        ).order_by('purchase_date').values(
            'id', 'batch_number', 'purchase_date', 'remaining_quantity', 
            'purchase_price', 'selling_price'
        )

        return Response(list(batches))


class ComputerPurchaseViewSet(viewsets.ModelViewSet):
    """Computer purchase management viewset."""
    queryset = ComputerPurchase.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]
    pagination_class = PageNumberPagination

    def get_serializer_class(self):
        return ComputerPurchaseSerializer

    def get_queryset(self):
        queryset = ComputerPurchase.objects.all().select_related('brand', 'model', 'customer', 'handled_by')

        # Filter by user's shop unless super admin
        if not self.request.user.is_super_admin():
            queryset = queryset.filter(shop=self.request.user.shop)

        # Filter by brand
        brand = self.request.query_params.get('brand')
        if brand:
            queryset = queryset.filter(brand__name__icontains=brand)

        # Filter by model
        model = self.request.query_params.get('model')
        if model:
            queryset = queryset.filter(model__name__icontains=model)

        # Filter by customer
        customer = self.request.query_params.get('customer')
        if customer:
            queryset = queryset.filter(customer_name__icontains=customer)

        # Filter by grade
        grade = self.request.query_params.get('grade')
        if grade:
            queryset = queryset.filter(grade=grade)

        # Search by customer name or IMEI
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(customer_name__icontains=search) |
                Q(imei_number__icontains=search) |
                Q(customer_phone__icontains=search)
            )

        return queryset.order_by('-purchase_date')



    @action(detail=False, methods=['get'], url_path='mobile-purchase-summary')
    @swagger_auto_schema(
        operation_description="Get mobile purchase summary statistics",
        responses={200: 'Mobile purchase summary statistics'}
    )
    def mobile_purchase_summary(self, request):
        """Get mobile purchase summary statistics."""
        total_purchases = MobilePurchase.objects.all().count()
        total_value = MobilePurchase.objects.all().aggregate(
            total=Sum('purchase_price')
        )['total'] or 0

        # Grade distribution
        grade_stats = MobilePurchase.objects.all().values('grade').annotate(
            count=Count('id')
        ).order_by('grade')

        # Monthly purchases (current year)
        from django.db.models.functions import TruncMonth
        monthly_stats = MobilePurchase.objects.filter(
            purchase_date__year=models.functions.Now().year
        ).annotate(
            month=TruncMonth('purchase_date')
        ).values('month').annotate(
            count=Count('id'),
            total_value=Sum('purchase_price')
        ).order_by('month')

        return Response({
            'total_purchases': total_purchases,
            'total_value': total_value,
            'grade_distribution': grade_stats,
            'monthly_stats': monthly_stats
        })


class DashboardStatsView(APIView):
    """Dashboard statistics view."""
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]

    @swagger_auto_schema(
        operation_description="Get comprehensive dashboard statistics",
        responses={200: 'Dashboard statistics'}
    )
    def get(self, request):
        """Get comprehensive dashboard statistics."""
        from django.db.models import Sum, Count, Q
        from datetime import datetime, timedelta
        from sales.models import Sale
        from customers.models import Customer
        
        # Get today's date
        today = datetime.now().date()
        month_start = today.replace(day=1)
        
        # Sales stats
        today_sales = Sale.objects.filter(sale_date=today, is_completed=True, is_cancelled=False)
        month_sales = Sale.objects.filter(sale_date__gte=month_start, is_completed=True, is_cancelled=False)
        
        today_sales_data = today_sales.aggregate(
            total_revenue=Sum('total_amount'),
            total_count=Count('id')
        )
        
        month_sales_data = month_sales.aggregate(
            total_revenue=Sum('total_amount'),
            total_count=Count('id')
        )
        
        # Inventory stats
        total_products = Product.objects.filter(is_active=True).count()
        low_stock_products = Product.objects.filter(is_active=True).annotate(
            total_stock=Coalesce(Sum('purchases__remaining_quantity'), Value(0))
        ).filter(total_stock__lte=F('min_stock_level')).count()

        # Mobile stats
        total_mobile_purchases = MobilePurchase.objects.all().count()
        available_mobiles = MobilePurchase.objects.filter(sold=False).count()

        # Customer stats
        customers_with_balance = Customer.objects.filter(current_balance__gt=0).count()
        total_outstanding = Customer.objects.aggregate(
            total=Sum('current_balance')
        )['total'] or 0

        # Repair stats
        pending_repairs = MobileRepair.objects.filter(status='pending').count()
        in_progress_repairs = MobileRepair.objects.filter(status='in_progress').count()

        return Response({
            'sales': {
                'today_revenue': today_sales_data['total_revenue'] or 0,
                'today_profit': 0,  # Would be calculated from profit margins
                'today_sales_count': today_sales_data['total_count'] or 0,
                'month_revenue': month_sales_data['total_revenue'] or 0,
                'month_profit': 0,  # Would be calculated from profit margins
                'month_sales_count': month_sales_data['total_count'] or 0
            },
            'inventory': {
                'total_products': total_products,
                'low_stock_products': low_stock_products,
                'total_mobile_purchases': total_mobile_purchases,
                'available_mobiles': available_mobiles
            },
            'customers': {
                'total_customers': Customer.objects.filter(is_active=True).count(),
                'customers_with_balance': customers_with_balance,
                'total_outstanding': total_outstanding
            },
            'services': {
                'pending_repairs': pending_repairs,
                'in_progress_repairs': in_progress_repairs
            }
        })


class UnifiedSearchPagination(PageNumberPagination):
    """Custom pagination for unified search results."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class UnifiedSearchViewSet(viewsets.ViewSet):
    """Unified search viewset for products and mobile purchases."""
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]
    pagination_class = UnifiedSearchPagination

    @swagger_auto_schema(
        operation_description="Search across products and mobile purchases",
        manual_parameters=[
            openapi.Parameter('q', openapi.IN_QUERY, description="Search query", type=openapi.TYPE_STRING)
        ],
        responses={200: 'Unified search results'}
    )
    def list(self, request):
        """Search across products and mobile purchases."""
        search_query = request.query_params.get('q', '').strip()

        if not search_query:
            return Response({
                'results': [],
                'count': 0,
                'next': None,
                'previous': None
            })

        # Build Q objects for flexible search
        product_q = Q(
            Q(name__icontains=search_query) |
            Q(item_code__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(category__name__icontains=search_query)
        ) & Q(is_active=True)

        mobile_q = Q(
            Q(brand__name__icontains=search_query) |
            Q(model__name__icontains=search_query) |
            Q(color__icontains=search_query) |
            Q(imei_number__icontains=search_query) |
            Q(customer_name__icontains=search_query)
        )

        # Get latest selling price from product purchases
        latest_purchase_subquery = ProductPurchase.objects.filter(
            product=OuterRef('pk'),
            remaining_quantity__gt=0
        ).order_by('-purchase_date').values('selling_price')[:1]

        # Get querysets - products with latest selling price from batches
        products = Product.objects.filter(product_q).annotate(
            search_type=models.Value('Product', output_field=models.CharField()),
            display_name=models.F('name'),
            display_price=Coalesce(Subquery(latest_purchase_subquery), Value(0), output_field=models.DecimalField()),
            stock_available=Value(1, output_field=models.IntegerField())  # Placeholder - will be calculated properly later
        ).values(
            'id', 'search_type', 'display_name', 'display_price',
            'stock_available', 'item_code', 'category'
        )

        mobiles = MobilePurchase.objects.filter(mobile_q).annotate(
            search_type=models.Value('Mobile Purchase', output_field=models.CharField()),
            display_name=models.functions.Concat(
                models.F('customer_name'),
                models.Value(' - '),
                'brand__name',
                models.Value(' '),
                'model__name',
                models.Value(' ('),
                models.F('color'),
                models.Value(')')
            ),
            display_price=models.F('purchase_price'),
            stock_available=models.Value(1, output_field=models.IntegerField())
        ).values(
            'id', 'search_type', 'display_name', 'display_price',
            'stock_available', 'customer_name', 'imei_number'
        )

        # Combine and sort results
        combined_results = list(products) + list(mobiles)

        # Sort by relevance (products first, then mobiles)
        combined_results.sort(key=lambda x: (x['search_type'] != 'Product', x['display_name']))

        # Paginate results
        paginator = self.pagination_class()
        paginated_results = paginator.paginate_queryset(combined_results, request)

        return paginator.get_paginated_response(paginated_results)


# ===== NEW FEATURE VIEWSETS =====

class SupplierViewSet(viewsets.ModelViewSet):
    """Supplier management viewset."""
    queryset = Supplier.objects.filter(is_active=True)
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        queryset = Supplier.objects.filter(is_active=True)

        # Filter by user's shop unless super admin
        if not self.request.user.is_super_admin():
            queryset = queryset.filter(shop=self.request.user.shop)

        # Search by name or contact person
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(contact_person__icontains=search)
            )

        return queryset.order_by('name')


class ComputerRepairViewSet(viewsets.ModelViewSet):
    """Computer repair management viewset."""
    queryset = ComputerRepair.objects.all()
    serializer_class = ComputerRepairSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        queryset = ComputerRepair.objects.all()

        # Filter by user's shop unless super admin
        if not self.request.user.is_super_admin():
            queryset = queryset.filter(shop=self.request.user.shop)

        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by technician
        technician = self.request.query_params.get('technician')
        if technician:
            queryset = queryset.filter(assigned_technician=technician)

        # Search by customer name or device model
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(customer_name__icontains=search) |
                Q(brand__icontains=search) |
                Q(model__icontains=search)
            )

        return queryset.order_by('-received_date')




class ComputerBrandViewSet(viewsets.ModelViewSet):
    """Computer brand management viewset."""
    queryset = ComputerBrand.objects.filter(is_active=True)
    serializer_class = ComputerBrandSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        queryset = ComputerBrand.objects.filter(is_active=True)

        # Filter by user's shop unless super admin
        if not self.request.user.is_super_admin():
            queryset = queryset.filter(shop=self.request.user.shop)

        # Search by name
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)

        return queryset.order_by('name')


class ComputerModelViewSet(viewsets.ModelViewSet):
    """Computer model management viewset."""
    queryset = ComputerModel.objects.filter(is_active=True)
    serializer_class = ComputerModelSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        queryset = ComputerModel.objects.filter(is_active=True)

        # Filter by user's shop unless super admin
        if not self.request.user.is_super_admin():
            queryset = queryset.filter(shop=self.request.user.shop)

        # Filter by brand
        brand_id = self.request.query_params.get('brand_id')
        if brand_id:
            queryset = queryset.filter(brand_id=brand_id)

        # Search by name
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)

        return queryset.order_by('brand', 'name')


class ComputerImageViewSet(viewsets.ModelViewSet):
    """Computer image management viewset with CRUD operations."""
    queryset = ComputerImage.objects.all()
    serializer_class = ComputerImageSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        queryset = ComputerImage.objects.all()
        
        # Filter by user's shop unless super admin
        if not self.request.user.is_super_admin():
            queryset = queryset.filter(shop=self.request.user.shop)
        
        # Filter by computer purchase if provided
        computer_purchase_id = self.request.query_params.get('computer_purchase_id')
        if computer_purchase_id:
            queryset = queryset.filter(computer_purchase_id=computer_purchase_id)
        
        return queryset.order_by('-is_main', 'created_at')

    @action(detail=True, methods=['post'])
    def set_main(self, request, pk=None):
        """Set this image as the main image for the computer purchase."""
        image = self.get_object()
        computer_purchase = image.computer_purchase
        
        # Unset all other main images for this computer purchase
        ComputerImage.objects.filter(
            computer_purchase=computer_purchase,
            is_main=True
        ).update(is_main=False)
        
        # Set this image as main
        image.is_main = True
        image.save()
        
        return Response({'message': 'Main image set successfully'}, status=status.HTTP_200_OK)
