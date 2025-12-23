from rest_framework import serializers
from .models import Product, Category, Shop, PriceHistory


class CategorySerializer(serializers.ModelSerializer):
    # Category serializer for API
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'is_active', 'product_count', 'created_at']
    
    def get_product_count(self, obj):
        # Count all products in this category (including unavailable)
        return obj.products.count()


class ShopSerializer(serializers.ModelSerializer):
    # Shop serializer for API
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Shop
        fields = ['id', 'name', 'slug', 'logo_url', 'website_url', 'is_active', 'priority', 'product_count']
    
    def get_product_count(self, obj):
        # Count all products in this shop (including unavailable)
        return obj.products.count()


class PriceHistorySerializer(serializers.ModelSerializer):
    # Price history serializer
    class Meta:
        model = PriceHistory
        fields = ['id', 'price', 'stock_status', 'recorded_at']


class ProductListSerializer(serializers.ModelSerializer):
    # Lightweight serializer for product lists
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    shop_logo = serializers.CharField(source='shop.logo_url', read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'category_name', 'category_slug',
            'shop_name', 'shop_logo', 'image_url', 'product_url',
            'current_price', 'stock_status', 'is_available', 'currency',
            'created_at', 'updated_at'
        ]


class ProductDetailSerializer(serializers.ModelSerializer):
    # Detailed serializer for single product view
    category = CategorySerializer(read_only=True)
    shop = ShopSerializer(read_only=True)
    price_history = serializers.SerializerMethodField()
    lowest_price = serializers.SerializerMethodField()
    highest_price = serializers.SerializerMethodField()
    average_price = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = '__all__'
    
    def get_price_history(self, obj):
        # Get last 30 days of price history
        from django.utils import timezone
        from datetime import timedelta
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        history = obj.price_history.filter(recorded_at__gte=thirty_days_ago).order_by('-recorded_at')[:30]
        return PriceHistorySerializer(history, many=True).data
    
    def get_lowest_price(self, obj):
        # Get lowest price from history
        history = obj.price_history.all()
        if history.exists():
            return float(min(h.price for h in history))
        return float(obj.current_price)
    
    def get_highest_price(self, obj):
        # Get highest price from history
        history = obj.price_history.all()
        if history.exists():
            return float(max(h.price for h in history))
        return float(obj.current_price)
    
    def get_average_price(self, obj):
        # Get average price from history
        history = obj.price_history.all()
        if history.exists():
            return round(sum(float(h.price) for h in history) / len(history), 2)
        return float(obj.current_price)
