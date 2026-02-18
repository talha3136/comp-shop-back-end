from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum, Count, Avg, F
from django.utils import timezone
from datetime import datetime, timedelta
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Sale, SaleItem, SalePayment
from .serializers import (
    SaleSerializer, SaleItemSerializer, SalePaymentSerializer, POSSaleCreateSerializer, SaleReceiptSerializer
)
from accounts.permissions import IsStaffUser

class SalePagination(PageNumberPagination):
    """Custom pagination for sales."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class SaleViewSet(viewsets.ModelViewSet):
    """Sale management viewset with CRUD operations and custom actions."""
    queryset = Sale.objects.filter(is_cancelled=False)
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]
    pagination_class = SalePagination

    def get_serializer_class(self):
        return SaleSerializer

    def get_queryset(self):
        queryset = Sale.objects.all()

        # Apply filters
        filters = {}
        exclude_filters = {}

        # Date range filter
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            filters['sale_date__gte'] = start_date
        if end_date:
            filters['sale_date__lte'] = end_date

        # Customer filter
        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            filters['customer_id'] = customer_id

        # Staff filter
        sold_by_id = self.request.query_params.get('sold_by_id')
        if sold_by_id:
            filters['sold_by_id'] = sold_by_id

        # Payment method filter
        payment_method = self.request.query_params.get('payment_method')
        if payment_method:
            filters['payment_method'] = payment_method

        # Amount range filters
        min_amount = self.request.query_params.get('min_amount')
        if min_amount:
            filters['total_amount__gte'] = min_amount

        max_amount = self.request.query_params.get('max_amount')
        if max_amount:
            filters['total_amount__lte'] = max_amount

        # Status filters
        status_filter = self.request.query_params.get('status')
        if status_filter == 'completed':
            filters['is_completed'] = True
            filters['is_cancelled'] = False
        elif status_filter == 'cancelled':
            filters['is_cancelled'] = True
        elif status_filter == 'pending':
            filters['is_completed'] = False
            filters['is_cancelled'] = False

        # Search functionality
        search = self.request.query_params.get('search', '').strip()
        if search:
            # Search by sale number, customer name, customer phone
            queryset = queryset.filter(
                Q(sale_number__icontains=search) |
                Q(customer_name__icontains=search) |
                Q(customer_phone__icontains=search)
            )

        # Apply filters
        queryset = queryset.filter(**filters)
        
        # Apply exclude filters if any
        if exclude_filters:
            queryset = queryset.exclude(**exclude_filters)

        return queryset.order_by('-sale_date')

    @action(detail=False, methods=['post'], url_path='pos-sale')
    @swagger_auto_schema(
        operation_description="Point of Sale interface for creating sales",
        request_body=POSSaleCreateSerializer,
        responses={201: 'Sale created successfully', 400: 'Bad request'}
    )
    def pos_sale(self, request):
        """Point of Sale interface for creating sales."""
        serializer = POSSaleCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        sale = serializer.save()

        return Response({
            'message': 'Sale created successfully',
            'sale': SaleSerializer(sale).data
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'post'], url_path='sale-receipt')
    @swagger_auto_schema(
        operation_description="Generate receipt for a sale",
        responses={200: SaleReceiptSerializer, 200: 'Receipt marked as printed'}
    )
    def sale_receipt(self, request, pk=None):
        """Generate receipt for a sale."""
        sale_id = pk
        sale = get_object_or_404(Sale, id=sale_id)

        if request.method == 'GET':
            # Get receipt data for printing
            serializer = SaleReceiptSerializer(sale)
            return Response(serializer.data)
        else:
            # Mark receipt as printed
            sale.print_receipt()
            return Response({'message': 'Receipt marked as printed'})

    @action(detail=True, methods=['post'], url_path='cancel-sale')
    @swagger_auto_schema(
        operation_description="Cancel a sale and restore product stock",
        responses={200: 'Sale cancelled successfully', 400: 'Bad request', 500: 'Server error'}
    )
    def cancel_sale(self, request, pk=None):
        """Cancel a sale and restore product stock."""
        sale_id = pk
        sale = get_object_or_404(Sale, id=sale_id)

        if sale.is_cancelled:
            return Response(
                {'error': 'Sale is already cancelled'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get restoration summary before cancelling
            restoration_summary = sale.get_stock_restoration_summary()

            # Restore stock for all sale items
            for item in sale.sale_items.all():
                item.restore_stock()

            # Mark sale as cancelled
            sale.is_cancelled = True
            sale.save()

            return Response({
                'message': 'Sale cancelled successfully and stock restored',
                'restoration_summary': restoration_summary
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to cancel sale: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, url_path='delete-sale',methods=['DELETE'])
    @swagger_auto_schema(
        operation_description="Permanently delete a sale and restore product stock",
        responses={200: 'Sale deleted successfully', 500: 'Server error'}
    )
    def delete_sale(self, request, pk=None):
        """Permanently delete a sale and restore product stock."""
        sale_id = pk
        sale = get_object_or_404(Sale, id=sale_id)

        try:
            # Get restoration summary before deleting
            restoration_summary = sale.get_stock_restoration_summary()

            # Restore stock for all sale items before deleting
            for item in sale.sale_items.all():
                item.restore_stock()

            # Handle credit sales - remove customer transaction
            if sale.payment_method == 'credit' and sale.customer:
                from customers.models import CustomerTransaction
                # Remove the debit transaction created during sale
                CustomerTransaction.objects.filter(
                    customer=sale.customer,
                    transaction_type='debit',
                    sale=sale
                ).delete()

            # Delete the sale (this will cascade delete sale items and payments)
            sale.delete()

            return Response({
                'message': 'Sale deleted successfully and stock restored',
                'restoration_summary': restoration_summary
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to delete sale: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='return-sale-items')
    @swagger_auto_schema(
        operation_description="Return specific items from a sale",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'items': openapi.Schema(
                    type=openapi.TYPE_ARRAY, 
                    description='Items to return',
                    items=openapi.Schema(type=openapi.TYPE_OBJECT)
                )
            },
            required=['items']
        ),
        responses={200: 'Items returned successfully', 400: 'Bad request', 500: 'Server error'}
    )
    def return_sale_items(self, request, pk=None):
        """Return specific items from a sale."""
        sale_id = pk
        sale = get_object_or_404(Sale, id=sale_id)
        return_data = request.data

        if not return_data or 'items' not in return_data:
            return Response(
                {'error': 'Items to return must be specified'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from decimal import Decimal
            returned_items = []
            total_refund = Decimal('0')
            total_profit_loss = Decimal('0')

            for return_item in return_data['items']:
                item_id = return_item.get('item_id')
                return_quantity = return_item.get('quantity', 0)
                refund_amount = return_item.get('refund_amount', 0)

                if not item_id or Decimal(str(return_quantity)) <= 0:
                    continue

                # Find the sale item
                try:
                    sale_item = sale.sale_items.get(id=item_id)
                except SaleItem.DoesNotExist:
                    continue

                # Check if return quantity is valid
                if Decimal(str(return_quantity)) > Decimal(str(sale_item.quantity)):
                    return Response(
                        {'error': f'Cannot return more than {sale_item.quantity} of {sale_item.product_name}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Calculate refund and profit loss
                return_quantity = Decimal(str(return_quantity))
                refund_amount = Decimal(str(refund_amount))
                
                unit_refund = refund_amount / return_quantity if return_quantity > 0 else Decimal('0')
                unit_cost = Decimal(str(sale_item.cost_price)) / Decimal(str(sale_item.quantity)) if sale_item.quantity > 0 else Decimal('0')
                profit_loss = (unit_refund - unit_cost) * return_quantity

                # Restore stock for returned quantity
                if sale_item.mobile_purchase:
                    # For mobile sales, mark as not sold
                    sale_item.mobile_purchase.sold = False
                    sale_item.mobile_purchase.save(update_fields=['sold'])
                elif sale_item.product_purchase:
                    # Restore to product batch
                    sale_item.product_purchase.adjust_stock(
                        quantity_change=int(return_quantity),
                        reason=f"Sale return - {sale.sale_number}"
                    )
                elif sale_item.product:
                    # Find latest batch
                    from inventory.models import ProductPurchase
                    latest_batch = ProductPurchase.objects.filter(
                        product=sale_item.product,
                        remaining_quantity__gt=0
                    ).order_by('-purchase_date').first()

                    if latest_batch:
                        latest_batch.adjust_stock(
                            quantity_change=int(return_quantity),
                            reason=f"Sale return - {sale.sale_number}"
                        )

                # Update sale item quantity and totals
                if return_quantity == Decimal(str(sale_item.quantity)):
                    # Full return - delete the item
                    sale_item.delete()
                else:
                    # Partial return - update quantities
                    sale_item.quantity -= int(return_quantity)
                    sale_item.total_price = sale_item.unit_price * sale_item.quantity
                    sale_item.profit = (sale_item.unit_price - sale_item.cost_price) * sale_item.quantity
                    sale_item.save()

                returned_items.append({
                    'item_name': sale_item.product_name,
                    'returned_quantity': return_quantity,
                    'refund_amount': refund_amount,
                    'profit_loss': profit_loss
                })

                total_refund += refund_amount
                total_profit_loss += profit_loss

            # Update sale totals
            sale.calculate_totals()
            sale.save()

            # Handle refund for credit sales
            if sale.payment_method == 'credit' and sale.customer and total_refund > Decimal('0'):
                from customers.models import CustomerTransaction
                CustomerTransaction.objects.create(
                    shop=sale.shop,
                    customer=sale.customer,
                    transaction_type='credit',  # Credit means customer owes less
                    amount=total_refund,
                    description=f"Return from Sale #{sale.sale_number}",
                    recorded_by=request.user,
                    sale=sale
                )

            return Response({
                'message': 'Items returned successfully',
                'returned_items': returned_items,
                'total_refund': total_refund,
                'total_profit_loss': total_profit_loss,
                'sale_updated': SaleSerializer(sale).data
            })

        except Exception as e:
            return Response(
                {'error': f'Failed to process return: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='daily-sales-report')
    @swagger_auto_schema(
        operation_description="Generate daily sales report",
        manual_parameters=[
            openapi.Parameter('date', openapi.IN_QUERY, description="Date (YYYY-MM-DD)", type=openapi.TYPE_STRING)
        ],
        responses={200: 'Daily sales report', 400: 'Invalid date format'}
    )
    def daily_sales_report(self, request):
        """Generate daily sales report."""
        date_str = request.query_params.get('date')
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            date = timezone.now().date()

        # Filter sales for the date
        sales = Sale.objects.filter(
            sale_date__date=date,
            is_cancelled=False
        )

        # Calculate totals
        total_sales = sales.count()
        total_amount = sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        total_profit = sales.aggregate(Sum('total_profit'))['total_profit__sum'] or 0

        # Payment method breakdown
        cash_sales = sales.filter(payment_method='cash').aggregate(
            Sum('total_amount')
        )['total_amount__sum'] or 0

        card_sales = sales.filter(payment_method='card').aggregate(
            Sum('total_amount')
        )['total_amount__sum'] or 0

        credit_sales = sales.filter(payment_method='credit').aggregate(
            Sum('total_amount')
        )['total_amount__sum'] or 0

        return Response({
            'date': date,
            'total_sales': total_sales,
            'total_amount': total_amount,
            'total_profit': total_profit,
            'cash_sales': cash_sales,
            'card_sales': card_sales,
            'credit_sales': credit_sales,
            'average_sale': total_amount / total_sales if total_sales > 0 else 0
        })

    @action(detail=False, methods=['get'], url_path='monthly-sales-report')
    @swagger_auto_schema(
        operation_description="Generate monthly sales report",
        manual_parameters=[
            openapi.Parameter('month', openapi.IN_QUERY, description="Month (1-12)", type=openapi.TYPE_INTEGER),
            openapi.Parameter('year', openapi.IN_QUERY, description="Year", type=openapi.TYPE_INTEGER)
        ],
        responses={200: 'Monthly sales report'}
    )
    def monthly_sales_report(self, request):
        """Generate monthly sales report."""
        month = int(request.query_params.get('month', timezone.now().month))
        year = int(request.query_params.get('year', timezone.now().year))

        # Filter sales for the month
        sales = Sale.objects.filter(
            sale_date__year=year,
            sale_date__month=month,
            is_cancelled=False
        )

        # Calculate totals
        total_sales = sales.count()
        total_amount = sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        total_profit = sales.aggregate(Sum('total_profit'))['total_profit__sum'] or 0

        return Response({
            'month': month,
            'year': year,
            'total_sales': total_sales,
            'total_amount': total_amount,
            'total_profit': total_profit,
            'average_sale': total_amount / total_sales if total_sales > 0 else 0
        })

    @action(detail=False, methods=['get'], url_path='sales-summary')
    @swagger_auto_schema(
        operation_description="Get sales summary for dashboard",
        responses={200: 'Sales summary data'}
    )
    def sales_summary(self, request):
        """Get sales summary for dashboard."""
        today = timezone.now().date()
        start_of_month = today.replace(day=1)

        # Today's sales
        today_sales = Sale.objects.filter(
            sale_date__date=today,
            is_cancelled=False
        )
        today_total = today_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        today_profit = today_sales.aggregate(Sum('total_profit'))['total_profit__sum'] or 0

        # This month's sales
        month_sales = Sale.objects.filter(
            sale_date__date__gte=start_of_month,
            is_cancelled=False
        )
        month_total = month_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        month_profit = month_sales.aggregate(Sum('total_profit'))['total_profit__sum'] or 0

        # Total sales count
        total_sales_count = Sale.objects.filter(is_cancelled=False).count()

        return Response({
            'today': {
                'sales_count': today_sales.count(),
                'total_amount': today_total,
                'total_profit': today_profit
            },
            'month': {
                'sales_count': month_sales.count(),
                'total_amount': month_total,
                'total_profit': month_profit
            },
            'overall': {
                'total_sales_count': total_sales_count
            }
        })

    @action(detail=False, methods=['get'], url_path='top-selling-products')
    @swagger_auto_schema(
        operation_description="Get top selling products",
        manual_parameters=[
            openapi.Parameter('days', openapi.IN_QUERY, description="Number of days", type=openapi.TYPE_INTEGER)
        ],
        responses={200: 'Top selling products'}
    )
    def top_selling_products(self, request):
        """Get top selling products."""
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)

        # Get top selling products
        top_products = SaleItem.objects.filter(
            sale__sale_date__gte=start_date,
            sale__is_cancelled=False,
            product__isnull=False
        ).values(
            'product_name', 'product_item_code'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum('total_price'),
            total_profit=Sum('profit')
        ).order_by('-total_quantity')[:10]

        return Response({
            'products': top_products
        })





class SalePaymentViewSet(viewsets.ModelViewSet):
    """Sale payment management viewset."""
    queryset = SalePayment.objects.all()
    serializer_class = SalePaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        queryset = SalePayment.objects.all()
        sale_id = self.kwargs.get('sale_pk')
        if sale_id:
            queryset = queryset.filter(sale_id=sale_id)
        return queryset

    def perform_create(self, serializer):
        """Set received_by to current user."""
        serializer.save(received_by=self.request.user)
