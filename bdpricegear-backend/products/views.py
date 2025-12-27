from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.shortcuts import get_object_or_404

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
        """Return all products by default, including unavailable ones."""
        queryset = super().get_queryset()
        # Optionally filter to show only available products
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


@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter(
            'product_id',
            openapi.IN_PATH,
            description="Product ID to compare prices across shops",
            type=openapi.TYPE_INTEGER,
            required=True
        ),
        openapi.Parameter(
            'days',
            openapi.IN_QUERY,
            description="Number of days of price history to include (default: 30)",
            type=openapi.TYPE_INTEGER,
            required=False
        )
    ],
    operation_description="Compare a specific product's price across different shops and show price history",
    responses={
        200: "Product price comparison with history",
        404: "Product not found"
    }
)
@api_view(['GET'])
def compare_product_prices(request, product_id):
    """
    Compare prices of a specific product from database across different shops.
    Shows current price, price history, and similar products from other shops.
    
    GET /api/products/{product_id}/compare/
    Query params:
    - days: Number of days of price history (default: 30, max: 90)
    """
    from datetime import timedelta
    from django.db.models import Q, Min, Max, Avg
    
    # Get the product
    product = get_object_or_404(Product.objects.select_related('category', 'shop'), id=product_id)
    
    # Get days parameter (default 30, max 90)
    days = int(request.GET.get('days', 30))
    days = min(max(days, 1), 90)  # Clamp between 1 and 90
    
    cutoff_date = timezone.now() - timedelta(days=days)
    
    # Get price history for this product
    price_history = product.price_history.filter(
        recorded_at__gte=cutoff_date
    ).order_by('-recorded_at')[:100]
    
    history_data = [{
        'price': float(h.price),
        'stock_status': h.stock_status,
        'date': h.recorded_at.strftime('%Y-%m-%d %H:%M')
    } for h in price_history]
    
    # Calculate price statistics
    history_prices = [float(h.price) for h in price_history if float(h.price) > 0]
    
    price_stats = {
        'current_price': float(product.current_price),
        'lowest_price': min(history_prices) if history_prices else float(product.current_price),
        'highest_price': max(history_prices) if history_prices else float(product.current_price),
        'average_price': round(sum(history_prices) / len(history_prices), 2) if history_prices else float(product.current_price),
        'price_trend': None
    }
    
    # Calculate trend (comparing first vs last 7 days)
    if len(history_prices) > 7:
        recent_avg = sum(history_prices[:7]) / 7
        older_avg = sum(history_prices[-7:]) / 7
        change_percent = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        
        if change_percent > 2:
            price_stats['price_trend'] = 'increasing'
        elif change_percent < -2:
            price_stats['price_trend'] = 'decreasing'
        else:
            price_stats['price_trend'] = 'stable'
    
    # Find similar products from other shops (same category, similar name)
    similar_products = Product.objects.filter(
        category=product.category,
        is_available=True
    ).exclude(
        id=product.id
    ).select_related('shop').order_by('current_price')[:10]
    
    # Group by shop and find best match
    shop_comparisons = {}
    for similar in similar_products:
        shop_name = similar.shop.name
        if shop_name not in shop_comparisons:
            # Calculate name similarity (simple word matching)
            product_words = set(product.name.lower().split())
            similar_words = set(similar.name.lower().split())
            common_words = len(product_words & similar_words)
            
            shop_comparisons[shop_name] = {
                'shop_id': similar.shop.id,
                'shop_name': shop_name,
                'shop_logo': similar.shop.logo_url,
                'product_id': similar.id,
                'product_name': similar.name,
                'product_url': similar.product_url,
                'price': float(similar.current_price),
                'stock_status': similar.stock_status,
                'similarity_score': common_words,
                'price_difference': float(similar.current_price - product.current_price)
            }
    
    # Convert to list and sort by price
    comparisons_list = sorted(
        shop_comparisons.values(),
        key=lambda x: x['price']
    )
    
    return Response({
        'product': {
            'id': product.id,
            'name': product.name,
            'category': product.category.name if product.category else None,
            'shop': product.shop.name,
            'shop_logo': product.shop.logo_url,
            'image_url': product.image_url,
            'product_url': product.product_url,
            'stock_status': product.stock_status,
            'is_available': product.is_available,
            'last_updated': product.updated_at.strftime('%Y-%m-%d %H:%M')
        },
        'price_stats': price_stats,
        'price_history': history_data,
        'similar_products_from_other_shops': comparisons_list,
        'metadata': {
            'history_days': days,
            'history_records': len(history_data),
            'shops_compared': len(comparisons_list)
        }
    })


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
            # Count all products (including unavailable)
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
            logger.info("🔄 Manual catalog update triggered via API")
            call_command('populate_catalog')  # Scrape all products from catalog pages
            
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


@api_view(['POST', 'GET'])
def cleanup_old_data(request):
    """
    Cleanup old price history data (3 months+)
    POST /api/cleanup/ - Trigger cleanup (async)
    GET /api/cleanup/ - Check cleanup status
    """
    from django.core.management import call_command
    from django.core.cache import cache
    from datetime import timedelta
    import threading
    
    cleanup_in_progress = cache.get('cleanup_in_progress', False)
    
    if request.method == 'GET':
        from products.models import PriceHistory
        
        total_records = PriceHistory.objects.count()
        cutoff_date = timezone.now() - timedelta(days=90)
        old_records = PriceHistory.objects.filter(recorded_at__lt=cutoff_date).count()
        
        last_cleanup = cache.get('last_cleanup_time', 'Never')
        
        return Response({
            "status": "ready",
            "message": "POST to trigger cleanup",
            "total_price_history_records": total_records,
            "records_older_than_90_days": old_records,
            "cleanup_in_progress": cleanup_in_progress,
            "last_cleanup": last_cleanup,
            "endpoint": "/api/cleanup/",
            "method": "POST"
        })
    
    # POST request - trigger cleanup
    if cleanup_in_progress:
        return Response({
            "status": "already_running",
            "message": " Cleanup already in progress"
        }, status=200)
    
    def run_cleanup():
        """Run cleanup in background thread"""
        try:
            cache.set('cleanup_in_progress', True, timeout=3600)
            logger.info(" Price history cleanup triggered via API")
            
            # Run cleanup command (90 days)
            from io import StringIO
            from datetime import timedelta
            from products.models import PriceHistory
            
            cutoff_date = timezone.now() - timedelta(days=90)
            old_records = PriceHistory.objects.filter(recorded_at__lt=cutoff_date)
            count = old_records.count()
            
            if count > 0:
                deleted_count, _ = old_records.delete()
                logger.info(f"Deleted {deleted_count:,} old price history records")
            else:
                logger.info("No old records to delete")
            
            cache.set('last_cleanup_time', timezone.now().isoformat(), timeout=None)
            cache.set('last_cleanup_deleted', count, timeout=None)
            cache.delete('cleanup_in_progress')
            
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")
            cache.delete('cleanup_in_progress')
    
    thread = threading.Thread(target=run_cleanup, daemon=True)
    thread.start()
    
    return Response({
        "status": "started",
        "message": "Price history cleanup started in background",
        "timestamp": timezone.now().isoformat(),
        "note": "Deleting records older than 90 days (3 months)"
    }, status=202)


@api_view(['POST', 'GET'])
def trigger_catalog_update(request):
    """
    Trigger catalog update (scrapes all pages from all websites)
    POST /api/catalog/update/ - Trigger full catalog scrape (NOT RECOMMENDED - use GitHub Actions)
    GET /api/catalog/update/ - Check catalog update status
    
    WARNING: This endpoint is disabled on production to prevent worker timeouts.
    Use GitHub Actions workflow instead for scheduled updates.
    """
    from django.core.management import call_command
    from django.core.cache import cache
    from django.db import connection
    import os
    
    # Check if running on Render
    is_production = os.environ.get('RENDER', False) or not DEBUG
    catalog_update_in_progress = cache.get('catalog_update_in_progress', False)
    
    if request.method == 'GET':
        from zoneinfo import ZoneInfo
        
        last_catalog_update = 'Never updated'
        last_error = cache.get('last_catalog_error', None)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT MAX(updated_at) FROM products_product")
                last_updated = cursor.fetchone()[0]
                
                if last_updated:
                    dt_dhaka = timezone.localtime(last_updated, ZoneInfo('Asia/Dhaka'))
                    last_catalog_update = dt_dhaka.strftime('%Y-%m-%d %I:%M %p %Z')
        except Exception:
            pass

        response_data = {
            "status": "ready",
            "message": "POST to trigger full catalog update",
            "last_catalog_update": last_catalog_update,
            "catalog_update_in_progress": catalog_update_in_progress,
            "endpoint": "/api/catalog/update/",
            "method": "POST",
            "note": "This scrapes all pages from all websites (takes longer)"
        }
        
        if last_error:
            response_data["last_error"] = last_error
            
        return Response(response_data)
    
    if catalog_update_in_progress:
        from zoneinfo import ZoneInfo
        last_catalog_update = 'Never updated'
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT MAX(updated_at) FROM products_product")
                last_updated = cursor.fetchone()[0]
                if last_updated:
                    dt_dhaka = timezone.localtime(last_updated, ZoneInfo('Asia/Dhaka'))
                    last_catalog_update = dt_dhaka.strftime('%Y-%m-%d %I:%M %p %Z')
        except Exception:
            pass
        
        return Response({
            "status": "already_running",
            "message": "Catalog update already in progress",
            "last_catalog_update": last_catalog_update
        }, status=200)
    
    # Prevent long-running tasks on production (Render) to avoid worker timeouts
    if is_production:
        return Response({
            "status": "disabled",
            "message": "Catalog update via API is disabled on production to prevent worker timeouts",
            "reason": "Long-running scraping tasks block Gunicorn workers causing timeouts",
            "recommendation": "Use GitHub Actions workflow for scheduled updates",
            "github_actions": "Hourly updates run automatically via .github/workflows/hourly-scrape.yml",
            "manual_trigger": "Trigger GitHub Actions manually from the Actions tab",
            "local_only": "This endpoint only works on local development (DEBUG=True)"
        }, status=503)
    
    # Only allow on local development
    def run_catalog_update():
        import sys
        try:
            cache.set('catalog_update_in_progress', True, timeout=7200)
            logger.info("="*80)
            logger.info("CATALOG UPDATE STARTED VIA API (LOCAL DEVELOPMENT ONLY)")
            logger.info("="*80)
            
            # Get categories from query parameter
            categories = request.GET.get('categories', '')
            if categories:
                category_list = [c.strip() for c in categories.split(',')]
                logger.info(f"Updating categories: {category_list}")
                call_command('populate_catalog', categories=category_list)
            else:
                logger.info("Updating all default categories")
                call_command('populate_catalog')
            
            cache.set('last_catalog_update', timezone.now().isoformat(), timeout=None)
            cache.delete('catalog_update_in_progress')
            logger.info("="*80)
            logger.info("CATALOG UPDATE COMPLETED SUCCESSFULLY")
            logger.info("="*80)
        except Exception as e:
            error_msg = f"Catalog update failed: {str(e)}"
            logger.error("="*80)
            logger.error(error_msg)
            logger.error("="*80)
            cache.delete('catalog_update_in_progress')
            cache.set('last_catalog_error', error_msg, timeout=3600)
    
    # Run synchronously on local development
    run_catalog_update()
    
    return Response({
        "status": "completed",
        "message": "Catalog update completed (local development only)",
        "timestamp": timezone.now().isoformat(),
        "note": "This endpoint is disabled on production. Use GitHub Actions for scheduled updates."
    }, status=200)


@api_view(['POST', 'GET'])
def cleanup_old_products(request):
    """
    Cleanup products not updated in 6 months
    POST /api/cleanup/products/ - Trigger product cleanup
    GET /api/cleanup/products/ - Check cleanup status
    """
    from django.core.management import call_command
    from django.core.cache import cache
    from datetime import timedelta
    import threading
    
    product_cleanup_in_progress = cache.get('product_cleanup_in_progress', False)
    
    if request.method == 'GET':
        from products.models import Product
        
        total_products = Product.objects.count()
        cutoff_date = timezone.now() - timedelta(days=180)
        old_products = Product.objects.filter(updated_at__lt=cutoff_date).count()
        
        last_product_cleanup = cache.get('last_product_cleanup_time', 'Never')
        
        return Response({
            "status": "ready",
            "message": "POST to trigger product cleanup",
            "total_products": total_products,
            "products_older_than_6_months": old_products,
            "product_cleanup_in_progress": product_cleanup_in_progress,
            "last_product_cleanup": last_product_cleanup,
            "endpoint": "/api/cleanup/products/",
            "method": "POST"
        })
    
    if product_cleanup_in_progress:
        return Response({
            "status": "already_running",
            "message": "Product cleanup already in progress"
        }, status=200)
    
    def run_product_cleanup():
        try:
            cache.set('product_cleanup_in_progress', True, timeout=3600)
            logger.info("Product cleanup triggered via API")
            
            from datetime import timedelta
            from products.models import Product
            
            cutoff_date = timezone.now() - timedelta(days=180)
            old_products = Product.objects.filter(updated_at__lt=cutoff_date)
            count = old_products.count()
            
            if count > 0:
                deleted_count, _ = old_products.delete()
                logger.info(f"Deleted {deleted_count:,} old products")
            else:
                logger.info("No old products to delete")
            
            cache.set('last_product_cleanup_time', timezone.now().isoformat(), timeout=None)
            cache.set('last_product_cleanup_deleted', count, timeout=None)
            cache.delete('product_cleanup_in_progress')
            
        except Exception as e:
            logger.error(f"Product cleanup failed: {str(e)}")
            cache.delete('product_cleanup_in_progress')
    
    thread = threading.Thread(target=run_product_cleanup, daemon=True)
    thread.start()
    
    return Response({
        "status": "started",
        "message": "Product cleanup started in background",
        "timestamp": timezone.now().isoformat(),
        "note": "Deleting products not updated in 6 months"
    }, status=202)
