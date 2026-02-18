from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Shop
from .serializers import ShopSerializer


class ShopViewSet(viewsets.ModelViewSet):
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer

    def get_queryset(self):
        # Filter by user's shop if user is authenticated
        user = self.request.user

        if not user.is_authenticated:
            return Shop.objects.none()

        if not hasattr(user, 'shop') or user.shop is None:
            return Shop.objects.none()

        return Shop.objects.filter(id=user.shop.id)

    @action(detail=False, methods=['get'], url_path='current')
    @swagger_auto_schema(
        operation_description="Get current user's shop",
        responses={200: ShopSerializer, 404: 'No shop associated with user'}
    )
    def current(self, request):
        """Get current user's shop"""
        user = request.user
        if user.is_authenticated and hasattr(user, 'shop'):
            shop = user.shop
            serializer = ShopSerializer(shop)
            return Response(serializer.data)
        return Response({"error": "No shop associated with user"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'], url_path='current-shop')
    @swagger_auto_schema(
        operation_description="Get current user's shop",
        responses={200: ShopSerializer, 404: 'No shop associated with user'}
    )
    def current_shop(self, request):
        """Get current user's shop"""
        user = request.user
        if user.is_authenticated and hasattr(user, 'shop'):
            shop = user.shop
            serializer = ShopSerializer(shop)
            return Response(serializer.data)
        return Response({"error": "No shop associated with user"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['put', 'patch'], url_path='update_current')
    @swagger_auto_schema(
        operation_description="Update current user's shop",
        request_body=ShopSerializer,
        responses={200: ShopSerializer, 400: 'Bad request', 404: 'No shop associated with user'}
    )
    def update_current(self, request):
        """Update current user's shop"""
        user = request.user
        if user.is_authenticated and hasattr(user, 'shop'):
            shop = user.shop
            serializer = ShopSerializer(shop, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response({"error": "No shop associated with user"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['put', 'patch'], url_path='update-current-shop')
    @swagger_auto_schema(
        operation_description="Update current user's shop",
        request_body=ShopSerializer,
        responses={200: ShopSerializer, 400: 'Bad request', 404: 'No shop associated with user'}
    )
    def update_current_shop(self, request):
        """Update current user's shop"""
        user = request.user
        if user.is_authenticated and hasattr(user, 'shop'):
            shop = user.shop
            serializer = ShopSerializer(shop, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response({"error": "No shop associated with user"}, status=status.HTTP_404_NOT_FOUND)