# Backend API Documentation - Current Structure

## Accounts App (prefix: /api/auth/)

### Authentication Endpoints
- `POST /login/` - CustomTokenObtainPairView (login with user data)
- `POST /token/refresh/` - CustomTokenRefreshView (token refresh)

### User Management Endpoints (UserViewSet)
- `GET /users/` - List users (admin only)
- `POST /users/` - Create user (admin only)
- `GET /users/<pk>/` - Retrieve user (admin or own profile)
- `PUT /users/<pk>/` - Update user (admin or own profile)
- `DELETE /users/<pk>/` - Delete user (admin only)
- `GET /users/profile/` - Get current user profile
- `PUT /users/profile/` - Update current user profile
- `PUT /users/change-password/` - Change password
- `GET /users/staff/` - List staff users (admin only)
- `GET /users/admins/` - List admin users (admin only)
- `POST /users/register/` - Register new user (admin only)
- `POST /users/logout/` - Logout user (blacklist refresh token)

## Customers App (prefix: /api/customers/)

### Customer Endpoints (CustomerViewSet)
- `GET /customers/` - List customers
- `POST /customers/` - Create customer
- `GET /customers/<pk>/` - Retrieve customer
- `PUT /customers/<pk>/` - Update customer
- `DELETE /customers/<pk>/` - Delete customer
- `GET /customers/<pk>/ledger/` - Get customer ledger
- `POST /customers/<pk>/balance_update/` - Update customer balance
- `GET /customers/search/` - Search customers
- `GET /customers/outstanding/` - List outstanding customers
- `GET /customers/summary/` - Get customer summary

### Transaction Endpoints (CustomerTransactionViewSet)
- `GET /customers/<customer_pk>/transactions/` - List customer transactions
- `POST /customers/<customer_pk>/transactions/` - Create customer transaction
- `GET /customers/<customer_pk>/transactions/<pk>/` - Retrieve transaction
- `PUT /customers/<customer_pk>/transactions/<pk>/` - Update transaction
- `DELETE /customers/<customer_pk>/transactions/<pk>/` - Delete transaction
- `POST /transactions/create_transaction/` - Create transaction (alternative)

## Inventory App (prefix: /api/inventory/)

### Product Endpoints (ProductViewSet)
- `GET /products/` - List products
- `POST /products/` - Create product
- `GET /products/<pk>/` - Retrieve product
- `PUT /products/<pk>/` - Update product
- `DELETE /products/<pk>/` - Delete product
- `POST /products/<pk>/generate_barcode/` - Generate barcode
- `POST /products/<pk>/update_stock/` - Update stock
- `GET /products/low_stock/` - List low stock products

### Computer Purchase Endpoints (ComputerPurchaseViewSet)
- `GET /computer-purchases/` - List computer purchases
- `POST /computer-purchases/` - Create computer purchase
- `GET /computer-purchases/<pk>/` - Retrieve computer purchase
- `PUT /computer-purchases/<pk>/` - Update computer purchase
- `DELETE /computer-purchases/<pk>/` - Delete computer purchase
- `POST /computer-purchases/<pk>/update_stock/` - Update stock

### Computer Sale Endpoints (ComputerSaleViewSet)
- `GET /computer-sales/` - List computer sales
- `GET /computer-sales/summary/` - Get inventory summary
- `GET /computer-sales/dashboard_stats/` - Get dashboard stats

### Supplier Endpoints (SupplierViewSet)
- `GET /suppliers/` - List suppliers
- `POST /suppliers/` - Create supplier
- `GET /suppliers/<pk>/` - Retrieve supplier
- `PUT /suppliers/<pk>/` - Update supplier
- `DELETE /suppliers/<pk>/` - Delete supplier

### Repair Endpoints (ComputerRepairViewSet)
- `GET /repairs/` - List repairs
- `POST /repairs/` - Create repair
- `GET /repairs/<pk>/` - Retrieve repair
- `PUT /repairs/<pk>/` - Update repair
- `DELETE /repairs/<pk>/` - Delete repair

### Exchange Endpoints (ComputerExchangeViewSet)
- `GET /exchanges/` - List exchanges
- `POST /exchanges/` - Create exchange
- `GET /exchanges/<pk>/` - Retrieve exchange
- `PUT /exchanges/<pk>/` - Update exchange
- `DELETE /exchanges/<pk>/` - Delete exchange

### Financing Endpoints (ComputerFinancingViewSet)
- `GET /emis/` - List EMIs
- `POST /emis/` - Create EMI
- `GET /emis/<pk>/` - Retrieve EMI
- `PUT /emis/<pk>/` - Update EMI
- `DELETE /emis/<pk>/` - Delete EMI

### EMI Installment Endpoints (EMIInstallmentViewSet)
- `GET /emis/<emi_pk>/installments/` - List EMI installments
- `POST /emis/<emi_pk>/installments/` - Create EMI installment
- `GET /emis/<emi_pk>/installments/<pk>/` - Retrieve installment
- `PUT /emis/<emi_pk>/installments/<pk>/` - Update installment
- `DELETE /emis/<emi_pk>/installments/<pk>/` - Delete installment

### Warranty Claim Endpoints (WarrantyClaimViewSet)
- `GET /warranty-claims/` - List warranty claims
- `POST /warranty-claims/` - Create warranty claim
- `GET /warranty-claims/<pk>/` - Retrieve warranty claim
- `PUT /warranty-claims/<pk>/` - Update warranty claim
- `DELETE /warranty-claims/<pk>/` - Delete warranty claim

### Insurance Claim Endpoints (InsuranceClaimViewSet)
- `GET /insurance-claims/` - List insurance claims
- `POST /insurance-claims/` - Create insurance claim
- `GET /insurance-claims/<pk>/` - Retrieve insurance claim
- `PUT /insurance-claims/<pk>/` - Update insurance claim
- `DELETE /insurance-claims/<pk>/` - Delete insurance claim



### Brand Endpoints (ComputerBrandViewSet)
- `GET /brands/` - List brands
- `POST /brands/` - Create brand
- `GET /brands/<pk>/` - Retrieve brand
- `PUT /brands/<pk>/` - Update brand
- `DELETE /brands/<pk>/` - Delete brand

### Model Endpoints (ComputerModelViewSet)
- `GET /models/` - List models
- `POST /models/` - Create model
- `GET /models/<pk>/` - Retrieve model
- `PUT /models/<pk>/` - Update model
- `DELETE /models/<pk>/` - Delete model

## Reports App (prefix: /api/reports/) - ReportViewSet

- `GET /reports/dashboard/` - Get dashboard summary
- `GET /reports/sales_analytics/` - Get sales analytics
- `GET /reports/profit/` - Generate profit report
- `GET /reports/inventory/` - Generate inventory report
- `GET /reports/customers/` - Generate customer report
- `GET /reports/business/` - Generate business report

## Sales App (prefix: /api/sales/)

### Sale Endpoints (SaleViewSet)
- `GET /sales/` - List sales
- `POST /sales/` - Create sale
- `GET /sales/<pk>/` - Retrieve sale
- `PUT /sales/<pk>/` - Update sale
- `DELETE /sales/<pk>/` - Delete sale
- `POST /sales/pos/` - Point of sale interface
- `GET /sales/<pk>/receipt/` - Get sale receipt
- `POST /sales/<pk>/receipt/` - Mark receipt as printed
- `POST /sales/<pk>/cancel/` - Cancel sale
- `GET /sales/daily_report/` - Generate daily sales report
- `GET /sales/monthly_report/` - Generate monthly sales report
- `GET /sales/summary/` - Get sales summary
- `GET /sales/top_products/` - Get top selling products

### Payment Endpoints (SalePaymentViewSet)
- `GET /sales/<sale_pk>/payments/` - List sale payments
- `POST /sales/<sale_pk>/payments/` - Create sale payment
- `GET /sales/<sale_pk>/payments/<pk>/` - Retrieve payment
- `PUT /sales/<sale_pk>/payments/<pk>/` - Update payment
- `DELETE /sales/<sale_pk>/payments/<pk>/` - Delete payment

---

## ✅ Conversion Complete

All views have been successfully converted to DRF Generic ViewSets with mixins and @action decorators:

1. **✅ Accounts App**: UserViewSet with actions for profile, change_password, staff_list, admin_list, register, logout
2. **✅ Customers App**: CustomerViewSet and CustomerTransactionViewSet with appropriate actions
3. **✅ Inventory App**: Multiple viewsets (ProductViewSet, ComputerPurchaseViewSet, etc.) with actions
4. **✅ Reports App**: ReportViewSet with multiple @action methods
5. **✅ Sales App**: SaleViewSet and SalePaymentViewSet with actions

**✅ URL Configuration**: All apps now use DefaultRouter for URL configuration instead of manual path() definitions.

**✅ Frontend Updates**: Updated auth store to use new API endpoints.

**✅ Testing**: Django server starts successfully with no system check issues.
