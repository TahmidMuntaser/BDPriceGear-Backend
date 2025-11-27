from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from .utils.cache_manager import price_cache
from .utils.scraper import (
    scrape_startech, scrape_ryans, scrape_skyland,
    scrape_pchouse, scrape_ultratech, scrape_binary_playwright, scrape_potakait
)
from .models import Product, Category, Shop
from .serializers import (
    ProductListSerializer, ProductDetailSerializer,
    CategorySerializer, ShopSerializer
)
from .filters import ProductFilter

import asyncio
import logging
import time
from playwright.async_api import async_playwright
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("products.views")

@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter(
            'product',
            openapi.IN_QUERY,
            description="Product name to search for (e.g., 'laptop', 'mouse', 'keyboard')",
            type=openapi.TYPE_STRING,
            required=True
        )
    ],
    operation_description="Compare product prices across multiple Bangladeshi tech shops",
    responses={
        200: "List of shops with products and prices",
        400: "Missing product query parameter"
    }
)
@api_view(['GET', 'HEAD', 'OPTIONS'])
def price_comparison(request):
    
    # Handle CORS preflight requests
    if request.method == 'OPTIONS':
        return Response(status=200)
    
    if request.method == 'HEAD':   
        return Response(status=200)
    
    product = request.GET.get('product')
    
    if not product:
        return Response({"error": "Missing 'product' query parameter"}, status=400)
    
    # Check cache first
    cached_result = price_cache.get(product)
    if cached_result:
        logger.info(f"Cache hit for '{product}'")
        return Response(cached_result)
    
    # Clean up expired cache 
    price_cache.clear_expired()
    
    async def gather_all_scrapers(product):
        # Dynamic scrapers
        async def run_dynamic():
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled']
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={'width': 1920, 'height': 1080},
                    locale='en-US',
                    timezone_id='Asia/Dhaka',
                    extra_http_headers={
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    }
                )

                tasks = [
                    scrape_ryans(product, context),
                    scrape_binary_playwright(product, context) 
                ]
                results = await asyncio.gather(*tasks)
                await browser.close()
                return results

        # Static scrapers in thread pool
        def run_static():
            with ThreadPoolExecutor() as executor:
                tasks = [
                    executor.submit(scrape_startech, product),
                    executor.submit(scrape_skyland, product),
                    executor.submit(scrape_pchouse, product),
                    executor.submit(scrape_ultratech, product),
                    executor.submit(scrape_potakait, product),
                ]
                return [task.result() for task in tasks]

        # Run both dynamic and static in parallel
        loop = asyncio.get_event_loop()
        dynamic_task = run_dynamic()
        static_task = loop.run_in_executor(None, run_static)
        
        # Wait for both to complete
        dynamic_results, static_results = await asyncio.gather(dynamic_task, static_task)
        
        ryans, binary = dynamic_results
        startech, skyland, pchouse, ultratech, potakait = static_results
        
        return ryans, binary, startech, skyland, pchouse, ultratech, potakait

    ryans, binary, startech, skyland, pchouse, ultratech, potakait = asyncio.run(gather_all_scrapers(product))
    
    # combine scraper results
    all_shops = [
        {"name": "StarTech", **startech},
        {"name": "Ryans", **ryans},
        {"name": "SkyLand", **skyland},
        {"name": "PcHouse", **pchouse},
        {"name": "UltraTech", **ultratech},
        {"name": "Binary", **binary},
        {"name": "PotakaIT", **potakait},
    ]
    
    # filter empty results 
    shops_with_results = [shop for shop in all_shops if shop.get("products")]
    
    # Cache the results: 5 min
    price_cache.set(product, shops_with_results, ttl=300)
    logger.info(f"Cached results for '{product}' - Found {len(shops_with_results)} shops")
    
    return Response(shops_with_results)


# ========================================
# PRODUCT CATALOG API VIEWS
# ========================================

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    
    # API endpoint for browsing product catalog.
    
    # List: GET /api/products/
    # Detail: GET /api/products/{id}/
    
    # Filters:
    # - ?category=laptop
    # - ?shop=startech
    # - ?min_price=10000&max_price=50000
    # - ?search=gaming
    # - ?brand=asus
    # - ?in_stock=true
    # - ?on_sale=true
    # - ?show_unavailable=true (to include out of stock items)
    
    queryset = Product.objects.all().select_related('category', 'shop')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'brand', 'description']
    ordering_fields = ['current_price', 'created_at', 'discount_percentage', 'name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return all products by default, including out-of-stock and zero-price."""
        queryset = super().get_queryset()
        # If user explicitly requests only available products, filter them
        only_available = self.request.query_params.get('only_available', 'false').lower() == 'true'
        if only_available:
            queryset = queryset.filter(is_available=True)
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductListSerializer
    
    def retrieve(self, request, *args, **kwargs):
        # Get single product and increment view count
        instance = self.get_object()
        instance.views_count += 1
        instance.save(update_fields=['views_count'])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    # 
    # API endpoint for product categories.
    
    # List: GET /api/categories/
    # Detail: GET /api/categories/{id}/
    # 
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    lookup_field = 'slug'


class ShopViewSet(viewsets.ReadOnlyModelViewSet):
    
    # API endpoint for shops.
    
    # List: GET /api/shops/
    # Detail: GET /api/shops/{id}/
    
    queryset = Shop.objects.filter(is_active=True)
    serializer_class = ShopSerializer
    lookup_field = 'slug'


@api_view(['GET'])
def health_check(request):
    """
    Health check endpoint for monitoring
    Returns database status and product count
    """
    from django.db import connection
    from django.core.cache import cache
    from zoneinfo import ZoneInfo
    
    database_status = "disconnected"
    product_count = 0
    update_in_progress = cache.get('update_in_progress', False)

    # Get last scrape time from most recently updated product
    last_update_dhaka = 'Never updated'
    
    try:
        # Check database and get last update time
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM products_product")
            product_count = cursor.fetchone()[0]
            
            # Get the most recent updated_at timestamp
            cursor.execute("SELECT MAX(updated_at) FROM products_product")
            last_updated = cursor.fetchone()[0]
            
            if last_updated:
                # Convert to Dhaka timezone
                dt_dhaka = timezone.localtime(last_updated, ZoneInfo('Asia/Dhaka'))
                last_update_dhaka = dt_dhaka.strftime('%Y-%m-%d %I:%M %p %Z')  # Human-readable format
            
        database_status = "connected"
    except Exception as e:
        database_status = f"error: {str(e)}"
    
    return Response({
        "status": "ok",
        "timestamp": timezone.now().isoformat(),
        "service": "BDPriceGear Backend",
        "database": database_status,
        "products_in_db": product_count,
        "last_update": last_update_dhaka,
        "update_in_progress": update_in_progress,
        "scheduler": "GitHub Actions (hourly updates)",
        "update_method": "GitHub Actions triggers /api/update/ every hour"
    })


@api_view(['POST', 'GET'])
def trigger_update(request):
    """
    Manually trigger product update
    POST /api/products/update/ - Trigger immediate update (async)
    GET /api/products/update/status/ - Check last update time
    """
    from django.core.management import call_command
    from django.core.cache import cache
    from django.db import connection
    import threading
    
    update_in_progress = cache.get('update_in_progress', False)
    
    if request.method == 'GET':
        # Get last update from database (most recent product updated_at)
        from zoneinfo import ZoneInfo
        
        last_update_dhaka = 'Never updated'
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT MAX(updated_at) FROM products_product")
                last_updated = cursor.fetchone()[0]
                
                if last_updated:
                    dt_dhaka = timezone.localtime(last_updated, ZoneInfo('Asia/Dhaka'))
                    last_update_dhaka = dt_dhaka.strftime('%Y-%m-%d %I:%M %p %Z')
        except Exception:
            pass

        return Response({
            "status": "ready",
            "message": "POST to trigger update",
            "last_update": last_update_dhaka,
            "update_in_progress": update_in_progress,
            "endpoint": "/api/products/update/",
            "method": "POST"
        })
    
    # POST request - trigger update in background
    if update_in_progress:
        # Get last update from database for already_running response
        from zoneinfo import ZoneInfo
        last_update_dhaka = 'Never updated'
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT MAX(updated_at) FROM products_product")
                last_updated = cursor.fetchone()[0]
                if last_updated:
                    dt_dhaka = timezone.localtime(last_updated, ZoneInfo('Asia/Dhaka'))
                    last_update_dhaka = dt_dhaka.strftime('%Y-%m-%d %I:%M %p %Z')
        except Exception:
            pass
        
        return Response({
            "status": "already_running",
            "message": "⏳ Update already in progress",
            "last_update": last_update_dhaka
        }, status=200)
    
    def run_update():
        """Run update in background thread"""
        try:
            cache.set('update_in_progress', True, timeout=3600)  # 1 hour timeout
            logger.info("🔄 Manual update triggered via API")
            call_command('populate_products', limit=1500)  # Scrape all available products
            
            # Store update timestamp
            cache.set('last_product_update', timezone.now().isoformat(), timeout=None)
            cache.delete('update_in_progress')
            logger.info("✅ Product update completed")
        except Exception as e:
            logger.error(f"Update failed: {str(e)}")
            cache.delete('update_in_progress')
    
    # Start update in background thread
    thread = threading.Thread(target=run_update, daemon=True)
    thread.start()
    
    return Response({
        "status": "started",
        "message": "✅ Product update started in background",
        "timestamp": timezone.now().isoformat(),
        "note": "Check GET /api/update/ for status"
    }, status=202)  # 202 Accepted - processing started
