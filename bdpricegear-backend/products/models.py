from django.db import models
from django.core.validators import MinValueValidator, URLValidator
from django.utils import timezone
from django.utils.text import slugify


class Category(models.Model):
    # Product categories (e.g., Laptop, Mouse, Keyboard, Monitor)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Shop(models.Model):
    # E-commerce shops in Bangladesh
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    logo_url = models.URLField(max_length=500, blank=True, null=True)
    website_url = models.URLField(max_length=500)
    is_active = models.BooleanField(default=True)
    scraping_enabled = models.BooleanField(default=True, help_text="Enable/disable scraping for this shop")
    priority = models.IntegerField(default=0, help_text="Higher priority shops appear first")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', 'name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(models.Model):
    # Products scraped from various shops
    STOCK_STATUS = [
        ('in_stock', 'In Stock'),
        ('out_of_stock', 'Out of Stock'),
        ('pre_order', 'Pre-order'),
        ('discontinued', 'Discontinued'),
    ]
    
    # Product Identification
    name = models.CharField(max_length=500, db_index=True)
    slug = models.SlugField(max_length=500, blank=True, null=True)
    
    # Categorization
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='products')
    
    # Product Details
    description = models.TextField(blank=True, null=True)
    image_url = models.URLField(max_length=1000, blank=True, null=True)
    product_url = models.URLField(max_length=1000, validators=[URLValidator()])
    
    # Pricing
    current_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default='BDT')
    
    # Stock & Availability
    stock_status = models.CharField(max_length=20, choices=STOCK_STATUS, default='in_stock')
    is_available = models.BooleanField(default=True)
    
    # Tracking
    views_count = models.IntegerField(default=0)
    last_scraped = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['category', 'shop']),
            models.Index(fields=['stock_status', 'is_available']),
            models.Index(fields=['-created_at']),
        ]
        unique_together = ['shop', 'product_url']  # Prevent duplicate products
    
    def __str__(self):
        return f"{self.name} - {self.shop.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate slug
        if not self.slug:
            self.slug = slugify(self.name)[:500]
        
        # Update stock status based on price
        if isinstance(self.current_price, str) or self.current_price == 0:
            self.stock_status = 'out_of_stock'
            self.is_available = False
        
        super().save(*args, **kwargs)


class PriceHistory(models.Model):
    # Track price changes over time
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_history')
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    stock_status = models.CharField(max_length=20, choices=Product.STOCK_STATUS, default='in_stock')
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)
    
    class Meta:
        verbose_name_plural = "Price Histories"
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['product', '-recorded_at']),
        ]
    
    def __str__(self):
        return f"{self.product.name} - ৳{self.price} at {self.recorded_at.strftime('%Y-%m-%d %H:%M')}"

