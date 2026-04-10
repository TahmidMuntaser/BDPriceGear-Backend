from decimal import Decimal
import re

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
    best_alternatives = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = '__all__'

    def get_best_alternatives(self, obj):
        # Build a small, ordered set of same-category alternatives.
        if not obj.category_id or obj.current_price is None:
            return []

        try:
            current_price = Decimal(str(obj.current_price))
        except Exception:
            return []

        if current_price <= 0:
            return []
        category_queryset = Product.objects.filter(
            category_id=obj.category_id,
            is_available=True,
        ).exclude(
            id=obj.id
        ).select_related('shop')

        cheaper_products = list(
            category_queryset.filter(current_price__lt=current_price).order_by('-current_price', 'id')[:6]
        )
        similar_lower = current_price * Decimal('0.90')
        similar_upper = current_price * Decimal('1.10')
        similar_products = list(
            category_queryset.filter(
                current_price__gte=similar_lower,
                current_price__lte=similar_upper,
            ).order_by('current_price', 'id')[:6]
        )
        higher_products = list(
            category_queryset.filter(current_price__gt=current_price).order_by('current_price', 'id')[:6]
        )

        selected_products = []
        selected_ids = set()

        def product_brand(product):
            # Best-effort brand extraction from product title (first alphabetic token).
            words = re.findall(r"[A-Za-z][A-Za-z0-9+-]*", product.name or '')
            return words[0] if words else ''

        def format_amount(value):
            normalized = value.quantize(Decimal('0.01'))
            text = format(normalized, 'f').rstrip('0').rstrip('.')
            return text or '0'

        cheaper_products.sort(
            key=lambda product: (
                -Decimal(str(product.current_price)),
                product.id,
            )
        )
        similar_products.sort(
            key=lambda product: (
                abs(Decimal(str(product.current_price)) - current_price),
                Decimal(str(product.current_price)),
                product.id,
            )
        )
        higher_products.sort(
            key=lambda product: (
                Decimal(str(product.current_price)),
                product.id,
            )
        )

        def add_products(products, limit):
            added = 0
            for product in products:
                if product.id in selected_ids:
                    continue
                selected_ids.add(product.id)
                difference = Decimal(str(product.current_price)) - current_price
                price_label = f"+{format_amount(difference)} BDT"
                if difference < 0:
                    price_label = f"Save {format_amount(abs(difference))} BDT"
                elif difference == 0:
                    price_label = '0 BDT'

                selected_products.append({
                    'id': product.id,
                    'name': product.name,
                    'image': product.image_url,
                    'price': product.current_price,
                    'brand': product_brand(product),
                    'price_difference': difference,
                    'price_label': price_label,
                })
                added += 1
                if added >= limit:
                    break

        # Prefer cheaper options, then similar price, then upgrade options.
        add_products(cheaper_products, 3)
        add_products(similar_products, 2)
        add_products(higher_products, 1)

        # Top up to the requested 4-6 range if we have room and more unique items exist.
        if len(selected_products) < 4:
            for bucket in (cheaper_products, similar_products, higher_products):
                for product in bucket:
                    if len(selected_products) >= 6:
                        break
                    if product.id in selected_ids:
                        continue
                    add_products([product], 1)
                if len(selected_products) >= 6:
                    break

        return BestAlternativeSerializer(selected_products, many=True).data
    
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


class BestAlternativeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    image = serializers.CharField(allow_blank=True, allow_null=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    brand = serializers.CharField(allow_blank=True, allow_null=True)
    price_difference = serializers.DecimalField(max_digits=10, decimal_places=2)
    price_label = serializers.CharField()


class PopularProductSerializer(serializers.Serializer):
    
    #Lightweight serializer for the popular-products endpoint.
    #Accepts a dict produced by a raw SQL query (no ORM model instance required).
    
    id = serializers.IntegerField()
    name = serializers.CharField()
    category_name = serializers.CharField()
    category_slug = serializers.CharField()
    current_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    image_url = serializers.URLField()
    shop_name = serializers.CharField()
