from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from datetime import datetime, timedelta
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from sales.models import Sale, SaleItem
from inventory.models import Product, ComputerPurchase, ComputerRepair
from customers.models import Customer, CustomerTransaction
from accounts.permissions import IsStaffUser

class ReportViewSet(viewsets.ViewSet):
    """Report management viewset with various report actions."""
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]

    @action(detail=False, methods=['get'], url_path='dashboard-reports')
    @swagger_auto_schema(
        operation_description="Get dashboard summary data",
        responses={200: 'Dashboard summary data'}
    )
    def dashboard_reports(self, request):
        """Get dashboard summary data."""
        from django.db.models import Sum, Count, Q, F, Value
        from django.db.models.functions import Coalesce
        
        today = timezone.now().date()
        start_of_month = today.replace(day=1)

        # Sales data
        today_sales = Sale.objects.filter(
            sale_date__date=today,
            is_cancelled=False
        )
        today_revenue = today_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        today_profit = today_sales.aggregate(Sum('total_profit'))['total_profit__sum'] or 0

        month_sales = Sale.objects.filter(
            sale_date__date__gte=start_of_month,
            is_cancelled=False
        )
        month_revenue = month_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        month_profit = month_sales.aggregate(Sum('total_profit'))['total_profit__sum'] or 0

        # Inventory data with proper annotations
        products_with_stock = Product.objects.filter(is_active=True).annotate(
            total_stock=Sum('purchases__remaining_quantity')
        ).filter(total_stock__gt=0)
        
        total_products = Product.objects.filter(is_active=True).count()
        low_stock_products = products_with_stock.filter(
            total_stock__lte=F('min_stock_level')
        ).count()

        # Mobile data
        total_computer_purchases = ComputerPurchase.objects.all().count()
        available_computers = ComputerPurchase.objects.filter(sold=False).count()

        # Customer data
        total_customers = Customer.objects.filter(is_active=True).count()
        customers_with_balance = Customer.objects.filter(
            is_active=True,
            current_balance__gt=0
        ).count()

        total_outstanding = Customer.objects.filter(
            is_active=True,
            current_balance__gt=0
        ).aggregate(Sum('current_balance'))['current_balance__sum'] or 0

        # Service stats
        pending_repairs = ComputerRepair.objects.filter(status='pending').count()
        in_progress_repairs = ComputerRepair.objects.filter(status='in_progress').count()

        return Response({
            'sales': {
                'today_revenue': today_revenue,
                'today_profit': today_profit,
                'today_sales_count': today_sales.count(),
                'month_revenue': month_revenue,
                'month_profit': month_profit,
                'month_sales_count': month_sales.count()
            },
            'inventory': {
                'total_products': total_products,
                'low_stock_products': low_stock_products,
                'total_mobile_batches': total_mobile_purchases,
                'available_mobiles': available_mobiles
            },
            'customers': {
                'total_customers': total_customers,
                'customers_with_balance': customers_with_balance,
                'total_outstanding': total_outstanding
            },
            'services': {
                'pending_repairs': pending_repairs,
                'in_progress_repairs': in_progress_repairs,
                'active_emis': 0,  # To be implemented
                'overdue_emis': 0,  # To be implemented
                'pending_warranty_claims': 0,  # To be implemented
                'pending_insurance_claims': 0  # To be implemented
            }
        })

    @action(detail=False, methods=['get'], url_path='sales-analytics')
    @swagger_auto_schema(
        operation_description="Get detailed sales analytics",
        manual_parameters=[
            openapi.Parameter('days', openapi.IN_QUERY, description="Number of days for analytics", type=openapi.TYPE_INTEGER)
        ],
        responses={200: 'Sales analytics data'}
    )
    def sales_analytics(self, request):
        """Get detailed sales analytics."""
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)

        # Sales trend data (daily sales for the last N days)
        sales_trend = []
        for i in range(days):
            date = start_date + timedelta(days=i)
            day_sales = Sale.objects.filter(
                sale_date__date=date.date(),
                is_cancelled=False
            )
            sales_trend.append({
                'date': date.date(),
                'revenue': day_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
                'profit': day_sales.aggregate(Sum('total_profit'))['total_profit__sum'] or 0,
                'count': day_sales.count()
            })

        # Payment method breakdown
        payment_breakdown = Sale.objects.filter(
            sale_date__gte=start_date,
            is_cancelled=False
        ).values('payment_method').annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('-total')

        # Top selling products
        top_products = SaleItem.objects.filter(
            sale__sale_date__gte=start_date,
            sale__is_cancelled=False,
            product__isnull=False
        ).values('product_name').annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum('total_price')
        ).order_by('-total_quantity')[:10]

        # Top selling mobiles
        top_mobiles = []

        return Response({
            'sales_trend': sales_trend,
            'payment_breakdown': payment_breakdown,
            'top_products': top_products,
            'top_mobiles': top_mobiles
        })

    @action(detail=False, methods=['get'], url_path='profit-report')
    @swagger_auto_schema(
        operation_description="Generate profit report",
        manual_parameters=[
            openapi.Parameter('start_date', openapi.IN_QUERY, description="Start date (YYYY-MM-DD)", type=openapi.TYPE_STRING),
            openapi.Parameter('end_date', openapi.IN_QUERY, description="End date (YYYY-MM-DD)", type=openapi.TYPE_STRING)
        ],
        responses={200: 'Profit report data'}
    )
    def profit_report(self, request):
        """Generate profit report."""
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        else:
            start_date = timezone.now() - timedelta(days=30)

        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            end_date = timezone.now()

        # Sales profit
        sales = Sale.objects.filter(
            sale_date__date__gte=start_date.date(),
            sale_date__date__lte=end_date.date(),
            is_cancelled=False
        )

        total_sales_revenue = sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        total_profit = sales.aggregate(Sum('total_profit'))['total_profit__sum'] or 0
        total_cost = total_sales_revenue - total_profit

        # Product-wise profit
        product_profit = SaleItem.objects.filter(
            sale__sale_date__date__gte=start_date.date(),
            sale__sale_date__date__lte=end_date.date(),
            sale__is_cancelled=False,
            product__isnull=False
        ).values('product_name').annotate(
            total_revenue=Sum('total_price'),
            total_cost=Sum('cost_price' * F('quantity')),
            total_profit=Sum('profit')
        ).order_by('-total_profit')

        # Mobile-wise profit
        mobile_profit = []

        return Response({
            'period': {
                'start_date': start_date.date(),
                'end_date': end_date.date()
            },
            'summary': {
                'total_revenue': total_sales_revenue,
                'total_cost': total_cost,
                'total_profit': total_profit,
                'profit_margin': (total_profit / total_sales_revenue * 100) if total_sales_revenue > 0 else 0
            },
            'product_profit': product_profit,
            'mobile_profit': mobile_profit
        })

    @action(detail=False, methods=['get'], url_path='sales-summary')
    @swagger_auto_schema(
        operation_description="Get sales summary report",
        manual_parameters=[
            openapi.Parameter('start_date', openapi.IN_QUERY, description="Start date (YYYY-MM-DD)", type=openapi.TYPE_STRING),
            openapi.Parameter('end_date', openapi.IN_QUERY, description="End date (YYYY-MM-DD)", type=openapi.TYPE_STRING)
        ],
        responses={200: 'Sales summary report'}
    )
    def sales_summary(self, request):
        """Get sales summary report."""
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        else:
            start_date = timezone.now() - timedelta(days=30)

        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            end_date = timezone.now()

        # Sales data for the period
        sales = Sale.objects.filter(
            sale_date__date__gte=start_date.date(),
            sale_date__date__lte=end_date.date(),
            is_cancelled=False
        )

        total_sales = sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        total_profit = sales.aggregate(Sum('total_profit'))['total_profit__sum'] or 0
        total_transactions = sales.count()
        average_sale = total_sales / total_transactions if total_transactions > 0 else 0

        return Response({
            'total_sales': total_sales,
            'total_profit': total_profit,
            'total_transactions': total_transactions,
            'average_sale': average_sale
        })

    @action(detail=False, methods=['get'], url_path='top-products')
    def top_products(self, request):
        """Get top selling products."""
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        else:
            start_date = timezone.now() - timedelta(days=30)

        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            end_date = timezone.now()

        # Top selling products
        top_products = SaleItem.objects.filter(
            sale__sale_date__date__gte=start_date.date(),
            sale__sale_date__date__lte=end_date.date(),
            sale__is_cancelled=False,
            product__isnull=False
        ).values('product_name', 'product_item_code').annotate(
            product_id=F('product'),
            total_quantity=Sum('quantity'),
            total_revenue=Sum('total_price'),
            total_profit=Sum('profit')
        ).order_by('-total_quantity')[:20]

        return Response(list(top_products))

    @action(detail=False, methods=['get'], url_path='daily-reports')
    @swagger_auto_schema(
        operation_description="Get daily sales report",
        manual_parameters=[
            openapi.Parameter('start_date', openapi.IN_QUERY, description="Start date (YYYY-MM-DD)", type=openapi.TYPE_STRING),
            openapi.Parameter('end_date', openapi.IN_QUERY, description="End date (YYYY-MM-DD)", type=openapi.TYPE_STRING)
        ],
        responses={200: 'Daily sales report'}
    )
    def daily_reports(self, request):
        """Get daily sales report."""
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        else:
            start_date = timezone.now() - timedelta(days=30)

        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            end_date = timezone.now()

        # Daily sales data
        daily_sales = []
        current_date = start_date.date()
        end_date_obj = end_date.date()

        while current_date <= end_date_obj:
            day_sales = Sale.objects.filter(
                sale_date__date=current_date,
                is_cancelled=False
            )
            daily_sales.append({
                'date': current_date,
                'total_sales': day_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
                'total_profit': day_sales.aggregate(Sum('total_profit'))['total_profit__sum'] or 0,
                'total_transactions': day_sales.count()
            })
            current_date += timedelta(days=1)

        return Response(daily_sales)

    @action(detail=False, methods=['get'], url_path='monthly-reports')
    @swagger_auto_schema(
        operation_description="Get monthly sales report",
        manual_parameters=[
            openapi.Parameter('start_date', openapi.IN_QUERY, description="Start date (YYYY-MM-DD)", type=openapi.TYPE_STRING),
            openapi.Parameter('end_date', openapi.IN_QUERY, description="End date (YYYY-MM-DD)", type=openapi.TYPE_STRING)
        ],
        responses={200: 'Monthly sales report'}
    )
    def monthly_reports(self, request):
        """Get monthly sales report."""
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        else:
            start_date = timezone.now() - timedelta(days=365)

        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            end_date = timezone.now()

        # Monthly sales data
        monthly_sales = []
        current_date = start_date.replace(day=1)
        end_date_obj = end_date

        while current_date <= end_date_obj:
            month_start = current_date
            month_end = (current_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)

            month_sales = Sale.objects.filter(
                sale_date__date__gte=month_start.date(),
                sale_date__date__lte=min(month_end.date(), end_date_obj.date()),
                is_cancelled=False
            )

            monthly_sales.append({
                'date': month_start.strftime('%Y-%m'),
                'total_sales': month_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
                'total_profit': month_sales.aggregate(Sum('total_profit'))['total_profit__sum'] or 0,
                'total_transactions': month_sales.count()
            })

            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)

        return Response(monthly_sales)

    @action(detail=False, methods=['get'], url_path='inventory-reports')
    @swagger_auto_schema(
        operation_description="Generate inventory report",
        responses={200: 'Inventory report'}
    )
    def inventory_reports(self, request):
        """Generate inventory report."""
        from django.db.models import Sum, Count, Q, F, Value, Case, When, IntegerField
        from django.db.models.functions import Coalesce
        
        # Product inventory with annotations
        products_with_stock = Product.objects.filter(is_active=True).annotate(
            total_stock=Sum('purchases__remaining_quantity'),
            total_stock_value=Sum(F('purchases__remaining_quantity') * F('purchases__selling_price')),
            avg_cost_price=Sum(F('purchases__remaining_quantity') * F('purchases__purchase_price')) / Sum('purchases__remaining_quantity')
        ).filter(
            total_stock__gt=0
        ).values(
            'id', 'name', 'item_code', 'category__name', 'min_stock_level',
            'total_stock', 'total_stock_value', 'avg_cost_price'
        ).order_by('-total_stock_value')

        # Mark low stock items and add category
        products_list = []
        for product in products_with_stock:
            product_data = dict(product)
            product_data['is_low_stock'] = product['total_stock'] <= product['min_stock_level']
            product_data['category'] = product['category__name'] or 'Uncategorized'
            products_list.append(product_data)

        # Mobile inventory
        computers = ComputerPurchase.objects.filter(sold=False).values(
            'id', 'customer_name', 'brand__name', 'model__name', 'color', 
            'purchase_price', 'purchase_date'
        ).annotate(
            batch_value=F('purchase_price'),
            profit_per_unit=Value(0)  # Will be calculated when sold
        ).order_by('-purchase_date')

        # Low stock products count
        low_stock_products = Product.objects.filter(is_active=True).annotate(
            total_stock=Sum('purchases__remaining_quantity')
        ).filter(
            total_stock__lte=F('min_stock_level'),
            total_stock__gt=0
        ).count()

        # Total inventory value
        total_product_value = Product.objects.filter(is_active=True).aggregate(
            value=Sum(F('purchases__remaining_quantity') * F('purchases__selling_price'))
        )['value'] or 0

        total_computer_value = ComputerPurchase.objects.filter(sold=False).aggregate(
            value=Sum('purchase_price')
        )['value'] or 0

        return Response({
            'products': products_list,
            'computers': list(computers),
            'summary': {
                'total_products': Product.objects.filter(is_active=True).count(),
                'low_stock_products': low_stock_products,
                'total_product_value': total_product_value,
                'total_computer_value': total_computer_value,
                'total_inventory_value': total_product_value + total_computer_value
            }
        })

    @action(detail=False, methods=['get'], url_path='customer-reports')
    @swagger_auto_schema(
        operation_description="Generate customer report",
        responses={200: 'Customer report'}
    )
    def customer_reports(self, request):
        """Generate customer report."""
        # Customer statistics
        total_customers = Customer.objects.filter(is_active=True).count()

        customers_by_type = Customer.objects.filter(is_active=True).values(
            'customer_type'
        ).annotate(count=Count('id'))

        # Outstanding analysis
        outstanding_customers = Customer.objects.filter(
            is_active=True,
            current_balance__gt=0
        ).values('current_balance').annotate(
            count=Count('id')
        ).order_by('current_balance')

        # Recent transactions
        recent_transactions = CustomerTransaction.objects.select_related(
            'customer', 'recorded_by'
        ).order_by('-transaction_date')[:50]

        # Top customers by purchase amount
        top_customers = Customer.objects.filter(
            is_active=True
        ).values('name', 'phone', 'total_purchases').order_by(
            '-total_purchases'
        )[:20]

        return Response({
            'summary': {
                'total_customers': total_customers,
                'customers_by_type': customers_by_type
            },
            'outstanding_analysis': outstanding_customers,
            'recent_transactions': [
                {
                    'customer': t.customer.name,
                    'type': t.transaction_type,
                    'amount': t.amount,
                    'balance_after': t.balance_after,
                    'date': t.transaction_date,
                    'description': t.description
                } for t in recent_transactions
            ],
            'top_customers': top_customers
        })

    @action(detail=False, methods=['get'], url_path='business-reports')
    @swagger_auto_schema(
        operation_description="Generate comprehensive business report",
        manual_parameters=[
            openapi.Parameter('start_date', openapi.IN_QUERY, description="Start date (YYYY-MM-DD)", type=openapi.TYPE_STRING),
            openapi.Parameter('end_date', openapi.IN_QUERY, description="End date (YYYY-MM-DD)", type=openapi.TYPE_STRING)
        ],
        responses={200: 'Business report'}
    )
    def business_reports(self, request):
        """Generate comprehensive business report."""
        from django.db.models import Sum, Count, Q, F, Value
        from django.db.models.functions import Coalesce
        
        # Date range
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        else:
            start_date = timezone.now().replace(day=1)  # Start of current month

        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            end_date = timezone.now()

        # Sales metrics
        sales = Sale.objects.filter(
            sale_date__date__gte=start_date.date(),
            sale_date__date__lte=end_date.date(),
            is_cancelled=False
        )

        total_revenue = sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        total_profit = sales.aggregate(Sum('total_profit'))['total_profit__sum'] or 0
        total_sales_count = sales.count()

        # Cost of goods sold
        cogs = SaleItem.objects.filter(
            sale__sale_date__date__gte=start_date.date(),
            sale__sale_date__date__lte=end_date.date(),
            sale__is_cancelled=False
        ).aggregate(
            total_cost=Sum(F('cost_price') * F('quantity'))
        )['total_cost'] or 0

        # Customer metrics
        new_customers = Customer.objects.filter(
            is_active=True,
            created_at__date__gte=start_date.date(),
            created_at__date__lte=end_date.date()
        ).count()

        # Inventory turnover (simplified)
        total_product_value = Product.objects.filter(is_active=True).aggregate(
            value=Sum(F('purchases__remaining_quantity') * F('purchases__selling_price'))
        )['value'] or 0

        total_computer_value = ComputerPurchase.objects.filter(sold=False).aggregate(
            value=Sum('purchase_price')
        )['value'] or 0

        avg_inventory = (total_product_value + total_computer_value) / 2 if (total_product_value + total_computer_value) > 0 else 1

        inventory_turnover = cogs / avg_inventory if avg_inventory > 0 else 0

        return Response({
            'period': {
                'start_date': start_date.date(),
                'end_date': end_date.date()
            },
            'financial': {
                'total_revenue': total_revenue,
                'total_cost': cogs,
                'total_profit': total_profit,
                'profit_margin': (total_profit / total_revenue * 100) if total_revenue > 0 else 0
            },
            'operational': {
                'total_sales': total_sales_count,
                'average_sale_value': total_revenue / total_sales_count if total_sales_count > 0 else 0,
                'new_customers': new_customers,
                'inventory_turnover': inventory_turnover
            }
        })
