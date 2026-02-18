from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum, Count
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Customer, CustomerTransaction, CustomerDueReport
from .serializers import (
    CustomerSerializer, CustomerTransactionSerializer,
    CustomerLedgerSerializer, CustomerCreateTransactionSerializer
)
from accounts.permissions import IsStaffUser

class CustomerViewSet(viewsets.ModelViewSet):
    """Customer management viewset with CRUD operations and custom actions."""
    queryset = Customer.objects.all()  # Include both active and inactive customers
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]
    lookup_field = 'id'

    def get_serializer_class(self):
        return CustomerSerializer

    def get_queryset(self):
        """Simple base queryset - filtering moved to separate actions."""
        return Customer.objects.all().order_by('name')

    @action(detail=True, methods=['get'], url_path='customer-transactions')

    def customer_transactions(self, request, id):
        """Get customer transactions."""

        customer = get_object_or_404(Customer, id=id)
        transactions = CustomerTransaction.objects.filter(customer=customer).order_by('-transaction_date')
        serializer = CustomerTransactionSerializer(transactions, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='customer-ledger')
    @swagger_auto_schema(
        operation_description="Get customer ledger with transaction history",
        responses={200: CustomerLedgerSerializer()}
    )
    def customer_ledger(self, request, pk=None):
        """Get customer ledger with transaction history."""
        customer_id = pk
        customer = get_object_or_404(Customer, id=customer_id)
        serializer = CustomerLedgerSerializer(customer, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='balance-update')
    @swagger_auto_schema(
        operation_description="Update customer balance manually (for adjustments)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'new_balance': openapi.Schema(type=openapi.TYPE_NUMBER, description='New balance value')
            },
            required=['new_balance']
        ),
        responses={200: 'Balance updated successfully', 400: 'Bad request'}
    )
    def balance_update(self, request, pk=None):
        """Update customer balance manually (for adjustments)."""
        customer_id = pk
        customer = get_object_or_404(Customer, id=customer_id)

        new_balance = request.data.get('new_balance')
        if new_balance is None:
            return Response(
                {'error': 'new_balance is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            new_balance = float(new_balance)
        except (ValueError, TypeError):
            return Response(
                {'error': 'new_balance must be a valid number'},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_balance = customer.current_balance
        adjustment = new_balance - old_balance

        if adjustment != 0:
            # Create adjustment transaction
            transaction_type = 'credit' if adjustment > 0 else 'debit'
            CustomerTransaction.objects.create(
                customer=customer,
                transaction_type=transaction_type,
                amount=abs(adjustment),
                description='Balance adjustment',
                notes=f'Balance adjusted from {old_balance} to {new_balance}',
                recorded_by=request.user
            )

        return Response({
            'message': 'Balance updated successfully',
            'old_balance': old_balance,
            'new_balance': customer.current_balance
        })

    @action(detail=False, methods=['get'], url_path='customer-summary')
    @swagger_auto_schema(
        operation_description="Get customer summary statistics",
        responses={200: 'Customer summary statistics'}
    )
    def customer_summary(self, request):
        """Get customer summary statistics."""
        total_customers = Customer.objects.filter(is_active=True).count()
        customers_with_balance = Customer.objects.filter(
            is_active=True,
            current_balance__gt=0
        ).count()

        total_outstanding = Customer.objects.filter(
            is_active=True,
            current_balance__gt=0
        ).aggregate(Sum('current_balance'))['current_balance__sum'] or 0

        # Customer type breakdown
        regular_customers = Customer.objects.filter(
            is_active=True,
            customer_type='regular'
        ).count()

        wholesale_customers = Customer.objects.filter(
            is_active=True,
            customer_type='wholesale'
        ).count()

        vip_customers = Customer.objects.filter(
            is_active=True,
            customer_type='vip'
        ).count()

        # Recent transactions
        recent_transactions = CustomerTransaction.objects.all()[:10]

        return Response({
            'total_customers': total_customers,
            'customers_with_balance': customers_with_balance,
            'total_outstanding': total_outstanding,
            'customer_types': {
                'regular': regular_customers,
                'wholesale': wholesale_customers,
                'vip': vip_customers
            },
            'recent_transactions': CustomerTransactionSerializer(
                recent_transactions, many=True
            ).data
        })

    @action(detail=False, methods=['get'], url_path='filter-customers')
    @swagger_auto_schema(
        operation_description="Filter customers with various parameters",
        manual_parameters=[
            openapi.Parameter('is_active', openapi.IN_QUERY, description="Filter by active status", type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('search', openapi.IN_QUERY, description="Search by name or phone", type=openapi.TYPE_STRING),
            openapi.Parameter('customer_type', openapi.IN_QUERY, description="Filter by customer type", type=openapi.TYPE_STRING, enum=['regular', 'wholesale', 'vip']),
            openapi.Parameter('min_balance', openapi.IN_QUERY, description="Minimum balance", type=openapi.TYPE_NUMBER),
            openapi.Parameter('max_balance', openapi.IN_QUERY, description="Maximum balance", type=openapi.TYPE_NUMBER),
            openapi.Parameter('has_outstanding', openapi.IN_QUERY, description="Filter customers with outstanding balance", type=openapi.TYPE_BOOLEAN),
            openapi.Parameter('min_amount', openapi.IN_QUERY, description="Minimum outstanding amount (for has_outstanding=true)", type=openapi.TYPE_NUMBER)
        ],
        responses={200: CustomerSerializer(many=True)}
    )
    def filter_customers(self, request):
        """Filter customers with various parameters."""
        queryset = Customer.objects.all()

        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=(is_active.lower() == 'true'))
        else:
            # Default to active customers
            queryset = queryset.filter(is_active=True)

        # Search by name or phone
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(phone__icontains=search)
            )
            serializer = CustomerSerializer(queryset, many=True).data
            return Response(serializer)

        # Filter by customer type
        customer_type = self.request.query_params.get('customer_type')
        if customer_type:
            queryset = queryset.filter(customer_type=customer_type)

        # Filter by balance range
        min_balance = self.request.query_params.get('min_balance')
        max_balance = self.request.query_params.get('max_balance')
        if min_balance:
            queryset = queryset.filter(current_balance__gte=min_balance)
        if max_balance:
            queryset = queryset.filter(current_balance__lte=max_balance)

        # Filter customers with outstanding
        has_outstanding = self.request.query_params.get('has_outstanding')
        if has_outstanding == 'true':
            queryset = queryset.filter(current_balance__gt=0)
            # Filter by minimum outstanding amount if provided
            min_amount = self.request.query_params.get('min_amount')
            if min_amount:
                queryset = queryset.filter(current_balance__gte=min_amount)

        # Use pagination for consistent behavior with other endpoints
        page = self.paginate_queryset(queryset.order_by('name'))
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        # Fallback if pagination fails
        serializer = self.get_serializer(queryset.order_by('name'), many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='customers-by-type')
    @swagger_auto_schema(
        operation_description="Get customers by type",
        manual_parameters=[
            openapi.Parameter('customer_type', openapi.IN_QUERY, description="Customer type", type=openapi.TYPE_STRING, enum=['regular', 'wholesale', 'vip'], required=True)
        ],
        responses={200: CustomerSerializer(many=True)}
    )
    def customers_by_type(self, request):
        """Get customers by type."""
        customer_type = self.request.query_params.get('customer_type')
        if not customer_type:
            return Response(
                {'error': 'customer_type parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = Customer.objects.filter(
            is_active=True,
            customer_type=customer_type
        ).order_by('name')
        
        # Use pagination for consistent behavior
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        # Fallback if pagination fails
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class CustomerTransactionViewSet(viewsets.ModelViewSet):
    """Customer transaction management viewset."""
    queryset = CustomerTransaction.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]

    def get_serializer_class(self):
        return CustomerTransactionSerializer

    def get_queryset(self):
        """Filter transactions by customer if specified."""
        queryset = CustomerTransaction.objects.all()
        customer_id = self.kwargs.get('customer_pk')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        return queryset.order_by('-transaction_date')

    def perform_create(self, serializer):
        """Set recorded_by to current user."""
        serializer.save(recorded_by=self.request.user)

    @action(
        detail=False, 
        methods=['post'],
        url_path='create-transaction',
        )
    def create_transaction(self, request):
        """Create a customer transaction (debit/credit)."""
        serializer = CustomerCreateTransactionSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        # Create transaction using serializer's create method
        transaction = serializer.save()
        
        # Update customer balance
        customer = transaction.customer
        customer.current_balance = transaction.balance_after
        customer.save()

        return Response({
            'success': True,
            'message': 'Transaction created successfully',
            'transaction': CustomerTransactionSerializer(transaction).data,
            'new_balance': customer.current_balance
        }, status=status.HTTP_201_CREATED)
