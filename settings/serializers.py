from rest_framework import serializers
from .models import Shop


class ShopSerializer(serializers.ModelSerializer):
    user_count = serializers.SerializerMethodField()
    admin_count = serializers.SerializerMethodField()
    staff_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Shop
        fields = '__all__'
    
    def get_user_count(self, obj):
        return obj.users.count()
    
    def get_admin_count(self, obj):
        return obj.users.filter(role='admin').count()
    
    def get_staff_count(self, obj):
        return obj.users.filter(role='staff').count()


class ShopDetailSerializer(serializers.ModelSerializer):
    """Detailed shop serializer with user information"""
    users = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()
    admin_count = serializers.SerializerMethodField()
    staff_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Shop
        fields = '__all__'
    
    def get_users(self, obj):
        from accounts.serializers import UserSerializer
        return UserSerializer(obj.users.all(), many=True).data
    
    def get_user_count(self, obj):
        return obj.users.count()
    
    def get_admin_count(self, obj):
        return obj.users.filter(role='admin').count()
    
    def get_staff_count(self, obj):
        return obj.users.filter(role='staff').count()