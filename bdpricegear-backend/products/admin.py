from django.contrib import admin
from .models import Category, Shop, Product, PriceHistory


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'product_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'scraping_enabled', 'priority', 'product_count', 'created_at']
    list_filter = ['is_active', 'scraping_enabled', 'created_at']
    search_fields = ['name', 'website_url']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['is_active', 'scraping_enabled', 'priority']
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'shop', 'category', 'current_price', 'stock_status', 'is_available', 'last_scraped']
    list_filter = ['shop', 'category', 'stock_status', 'is_available', 'created_at']
    search_fields = ['name']
    readonly_fields = ['slug', 'views_count', 'last_scraped', 'created_at', 'updated_at']
    list_per_page = 50
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'category', 'shop')
        }),
        ('Product Details', {
            'fields': ('description', 'image_url', 'product_url')
        }),
        ('Pricing', {
            'fields': ('current_price', 'currency')
        }),
        ('Availability', {
            'fields': ('stock_status', 'is_available')
        }),
        ('Metadata', {
            'fields': ('views_count', 'last_scraped', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ['product', 'price', 'stock_status', 'recorded_at']
    list_filter = ['stock_status', 'recorded_at']
    search_fields = ['product__name']
    readonly_fields = ['product', 'price', 'stock_status', 'recorded_at']
    date_hierarchy = 'recorded_at'
    list_per_page = 100
    
    def has_add_permission(self, request):
        return False  # Don't allow manual addition
    
    def has_delete_permission(self, request, obj=None):
        return True  # Allow deletion of old records

