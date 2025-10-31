import django_filters
from .models import Product, Category, Shop


class ProductFilter(django_filters.FilterSet):
    # Filter for Product API
    
    # Text search
    search = django_filters.CharFilter(method='filter_search', label='Search')
    
    # Category filters
    category = django_filters.CharFilter(field_name='category__slug', lookup_expr='iexact')
    category_name = django_filters.CharFilter(field_name='category__name', lookup_expr='icontains')
    
    # Shop filters
    shop = django_filters.CharFilter(field_name='shop__slug', lookup_expr='iexact')
    shop_name = django_filters.CharFilter(field_name='shop__name', lookup_expr='icontains')
    
    # Price range filters
    min_price = django_filters.NumberFilter(field_name='current_price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='current_price', lookup_expr='lte')
    
    # Brand filter
    brand = django_filters.CharFilter(field_name='brand', lookup_expr='icontains')
    
    # Stock status
    in_stock = django_filters.BooleanFilter(method='filter_in_stock', label='In Stock')
    
    # Has discount
    on_sale = django_filters.BooleanFilter(method='filter_on_sale', label='On Sale')
    
    class Meta:
        model = Product
        fields = ['category', 'shop', 'brand', 'stock_status', 'is_available']
    
    def filter_search(self, queryset, name, value):
        # Search in product name, brand, and description
        return queryset.filter(
            models.Q(name__icontains=value) |
            models.Q(brand__icontains=value) |
            models.Q(description__icontains=value)
        )
    
    def filter_in_stock(self, queryset, name, value):
        # Filter products that are in stock
        if value:
            return queryset.filter(stock_status='in_stock', is_available=True)
        return queryset
    
    def filter_on_sale(self, queryset, name, value):
        # Filter products with discounts
        if value:
            return queryset.filter(discount_percentage__gt=0)
        return queryset


# Import models for Q lookups
from django.db import models
