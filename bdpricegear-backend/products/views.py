from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework import viewsets, filters, status, permissions
from rest_framework.decorators import action
from rest_framework.throttling import AnonRateThrottle
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.conf import settings

from .utils.cache_manager import price_cache
from .utils.scraper import (
    scrape_startech, scrape_skyland,
    scrape_pchouse, scrape_ultratech, scrape_potakait,
    scrape_computervillage, scrape_smartbd, scrape_selltech, scrape_globalbrand
)
from .models import Product, Category, Shop, Wishlist
from .models import Product, Category, Shop, Wishlist, StockSubscription
from .serializers import (
    ProductListSerializer, ProductDetailSerializer,
    CategorySerializer, ShopSerializer, PopularProductSerializer,
    WishlistInputSerializer, WishlistItemSerializer,
    StockSubscriptionInputSerializer, StockSubscriptionSerializer
)
from .filters import ProductFilter
from .utils.smart_search import apply_smart_search
from .pagination import FlexiblePagination

import asyncio
import logging
import time
import os
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("products.views")


class ScrapingRateThrottle(AnonRateThrottle):
    # Rate limit for scraping endpoints - 3 requests per hour per IP
    rate = '3/hour'


@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter(
            'q',
            openapi.IN_QUERY,
            description="Search query - supports product names, categories, and attributes (e.g., '8GB RAM', 'laptop', '512GB SSD')",
            type=openapi.TYPE_STRING,
            required=True
        ),
        openapi.Parameter(
            'page',
            openapi.IN_QUERY,
            description="Page number",
            type=openapi.TYPE_INTEGER,
            required=False
        ),
        openapi.Parameter(
            'page_size',
            openapi.IN_QUERY,
            description="Results per page (default 20, max 1000, or 'all')",
            type=openapi.TYPE_STRING,
            required=False
        )
    ],
    operation_description="Smart navbar search with intelligent category detection and filtering",
    responses={
        200: "List of matching products with pagination",
        400: "Missing query parameter"
    }
)
@api_view(['GET', 'HEAD', 'OPTIONS'])
@permission_classes([permissions.AllowAny])
def navbar_search(request):
    # Smart navbar search endpoint with product-list pagination pattern
    # GET /api/search/?q=<query>&page=1&page_size=20
    # Query params: q=search query (required), page=page number (optional), page_size=results per page (optional, supports 'all')
    # Features: category detection, text normalization (8GB, 8 GB, 8 gb work), category-aware filtering, prevents irrelevant mixing
    # Examples: /api/search/?q=laptop, /api/search/?q=laptop&page=2&page_size=20, /api/search/?q=8GB+RAM&page_size=all
    
    # Handle CORS preflight requests
    if request.method == 'OPTIONS':
        return Response(status=200)
    
    if request.method == 'HEAD':
        return Response(status=200)
    
    # Get search query
    query = request.GET.get('q', '').strip()
    
    if not query:
        return Response({
            "error": "Missing 'q' query parameter",
            "example": "/api/search/?q=laptop"
        }, status=400)
    
    # Get base queryset
    queryset = Product.objects.all().select_related('category', 'shop')
    
    # Apply smart search algorithm
    filtered_queryset = apply_smart_search(queryset, query)

    # Use the same pagination logic/shape as /api/products/
    paginator = FlexiblePagination()
    page = paginator.paginate_queryset(filtered_queryset, request)

    if page is not None:
        serializer = ProductListSerializer(page, many=True, context={'request': request})
        page_number = paginator.page.number
        total_pages = paginator.page.paginator.num_pages

        return Response({
            'count': paginator.page.paginator.count,
            'next': paginator.get_next_link(),
            'previous': paginator.get_previous_link(),
            'results': serializer.data,
            'pagination': {
                'current_page': page_number,
                'total_pages': total_pages,
                'page_size': len(serializer.data),
                'has_next': paginator.page.has_next(),
                'has_previous': paginator.page.has_previous(),
                'next_page': page_number + 1 if paginator.page.has_next() else None,
                'previous_page': page_number - 1 if paginator.page.has_previous() else None,
            },
        })

    serializer = ProductListSerializer(filtered_queryset, many=True, context={'request': request})
    return Response({
        'count': len(serializer.data),
        'next': None,
        'previous': None,
        'results': serializer.data,
    })

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
        with ThreadPoolExecutor() as executor:
            tasks = [
                executor.submit(scrape_startech, product),
                # executor.submit(scrape_ryans, product),  # Disabled for realtime scraping
                executor.submit(scrape_skyland, product),
                executor.submit(scrape_pchouse, product),
                executor.submit(scrape_ultratech, product),
                executor.submit(scrape_potakait, product),
                executor.submit(scrape_computervillage, product),
                executor.submit(scrape_smartbd, product),
                executor.submit(scrape_selltech, product),
                executor.submit(scrape_globalbrand, product),
            ]
            return [task.result() for task in tasks]

    (
        startech,
        # ryans,
        skyland,
        pchouse,
        ultratech,
        potakait,
        computervillage,
        smartbd,
        selltech,
        globalbrand,
    ) = asyncio.run(gather_all_scrapers(product))
    
    # combine scraper results
    all_shops = [
        {"name": "StarTech", **startech},
        # {"name": "Ryans", **ryans},
        {"name": "SkyLand", **skyland},
        {"name": "PcHouse", **pchouse},
        {"name": "UltraTech", **ultratech},
        {"name": "PotakaIT", **potakait},
        {"name": "ComputerVillage", **computervillage},
        {"name": "SmartBD", **smartbd},
        {"name": "SellTech", **selltech},
        {"name": "GlobalBrand", **globalbrand},
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
    # - ?in_stock=true
    # - ?on_sale=true
    # - ?show_unavailable=true (to include out of stock items)
    # - ?product=<name> (search for specific product by name)
    
    queryset = Product.objects.all().select_related('category', 'shop')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description']
    ordering_fields = ['current_price', 'created_at', 'discount_percentage', 'name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Return all products by default, including unavailable ones."""
        from django.db.models import Q
        
        queryset = super().get_queryset()
        
        # Handle ?product=<name> - search by category first, then by product name
        product_name = self.request.query_params.get('product', None)
        if product_name:
            search_term = product_name.strip()
            # First try to match category (most common use case)
            category_match = queryset.filter(
                Q(category__name__iexact=search_term) |
                Q(category__slug__iexact=search_term)
            )
            if category_match.exists():
                queryset = category_match
            else:
                # Fall back to product name search
                queryset = queryset.filter(name__icontains=search_term)
        
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

    @action(detail=True, methods=['get'], url_path='best-alternatives')
    def best_alternatives(self, request, *args, **kwargs):
        # Lightweight endpoint for frontend sections that only need recommendations.
        instance = self.get_object()
        recommendations = ProductDetailSerializer(instance).data.get('best_alternatives', [])
        return Response({
            'product_id': instance.id,
            'best_alternatives': recommendations,
        })


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


@api_view(['GET', 'HEAD', 'OPTIONS'])
@permission_classes([permissions.AllowAny])
def ping(request):
    # Lightweight liveness endpoint for uptime monitors.
    if request.method in ['HEAD', 'OPTIONS']:
        return Response(status=200)
    return Response({
        "status": "ok",
        "service": "BDPriceGear Backend"
    })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """
    Health check endpoint for monitoring
    Returns database status and product count
    """
    from django.db import connection, close_old_connections
    from django.core.cache import cache
    from zoneinfo import ZoneInfo
    
    # Close any stale connections before checking
    close_old_connections()
    
    database_status = "disconnected"
    product_count = 0
    update_in_progress = cache.get('update_in_progress', False)

    # Get last scrape time from most recently updated product
    last_update_dhaka = 'Never updated'
    
    try:
        # Check database and get last update time
        from django.db import OperationalError
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
    except (Exception, OperationalError) as e:
        logger.warning(f"Health check database query failed: {str(e)}")
        database_status = f"error: {str(e)}"
    finally:
        # Ensure connection is closed/returned to pool
        close_old_connections()
    
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
@permission_classes([permissions.AllowAny])
@throttle_classes([ScrapingRateThrottle])
def trigger_update(request):
    """
    Manually trigger product update
    POST /api/products/update/ - Trigger immediate update (async)
    GET /api/products/update/status/ - Check last update time
    """
    from django.core.management import call_command
    from django.core.cache import cache
    from django.db import connection, close_old_connections
    import threading
    
    # Close stale connections
    close_old_connections()
    
    # Get cache status (with fallback for cache setup issues)
    try:
        update_in_progress = cache.get('update_in_progress', False)
        last_error = cache.get('last_scraping_error', None)
    except Exception as cache_error:
        logger.error(f"Cache error: {cache_error}. Cache might not be set up. Run: python manage.py createcachetable")
        update_in_progress = False
        last_error = str(cache_error)
    
    if request.method == 'GET':
        # Get last update from database (most recent product updated_at)
        from zoneinfo import ZoneInfo
        
        last_update_dhaka = 'Never updated'
        try:
            from django.db import OperationalError
            with connection.cursor() as cursor:
                cursor.execute("SELECT MAX(updated_at) FROM products_product")
                last_updated = cursor.fetchone()[0]
                
                if last_updated:
                    dt_dhaka = timezone.localtime(last_updated, ZoneInfo('Asia/Dhaka'))
                    last_update_dhaka = dt_dhaka.strftime('%Y-%m-%d %I:%M %p %Z')
        except (Exception, OperationalError) as e:
            logger.warning(f"Database query failed: {str(e)}")
            last_update_dhaka = 'Database unavailable'
        finally:
            close_old_connections()

        response_data = {
            "status": "ready",
            "message": "POST to trigger update",
            "last_update": last_update_dhaka,
            "update_in_progress": update_in_progress,
            "endpoint": "/api/update/",
            "method": "POST"
        }
        
        # Include last error if exists
        if last_error:
            response_data["last_error"] = last_error
            response_data["error_help"] = "If cache error, run: python manage.py createcachetable"
        
        return Response(response_data)
    
    # POST request - acquire lock atomically (prevents race condition with concurrent requests)
    try:
        acquired = cache.add('update_in_progress', True, timeout=14400)  # 4 hours — must outlast the longest possible scrape
    except Exception as cache_err:
        logger.error(f"Cache error acquiring lock: {cache_err}")
        acquired = True  # if cache is broken, allow through

    if not acquired:
        # Get last update from database for already_running response
        from zoneinfo import ZoneInfo
        last_update_dhaka = 'Never updated'
        try:
            from django.db import OperationalError
            with connection.cursor() as cursor:
                cursor.execute("SELECT MAX(updated_at) FROM products_product")
                last_updated = cursor.fetchone()[0]
                if last_updated:
                    dt_dhaka = timezone.localtime(last_updated, ZoneInfo('Asia/Dhaka'))
                    last_update_dhaka = dt_dhaka.strftime('%Y-%m-%d %I:%M %p %Z')
        except (Exception, OperationalError) as e:
            logger.warning(f"Database query failed: {str(e)}")
            last_update_dhaka = 'Database unavailable'
        finally:
            close_old_connections()
        
        return Response({
            "status": "already_running",
            "message": "⏳ Update already in progress",
            "last_update": last_update_dhaka
        }, status=200)
    
    def run_update():
        """Run update using Django's call_command in background thread"""
        from django.core.management import call_command
        from django.db import close_old_connections, connection
        import traceback
        
        try:
            # Clear previous errors
            try:
                cache.delete('last_scraping_error')
            except Exception as cache_err:
                logger.error(f"Cache error during update start: {cache_err}")
            
            logger.info("🔄 Manual catalog update triggered via API")
            logger.info(f"Worker PID: {os.getpid()}, Thread: {threading.current_thread().name}")
            
            # Close any inherited connections - thread will create fresh ones
            close_old_connections()

            try:
                # Run Django management command directly
                logger.info("Starting populate_catalog command...")
                call_command('populate_catalog')

                logger.info("Product update completed successfully")
                
                # Store success timestamp
                try:
                    cache.set('last_product_update', timezone.now().isoformat(), timeout=None)
                    cache.set('last_update_status', 'success', timeout=None)
                except Exception as cache_err:
                    logger.error(f"Cache error during success save: {cache_err}")
                    
            except Exception as cmd_error:
                error_msg = str(cmd_error)
                error_output = traceback.format_exc()
                logger.error(f"Command failed: {error_msg}")
                
                # Store error details in cache
                try:
                    cache.set('last_scraping_error', f"{error_msg}\n{error_output[:500]}", timeout=86400)
                    cache.set('last_update_status', 'failed', timeout=None)
                except Exception as cache_err:
                    logger.error(f"Cache error during error save: {cache_err}")
                
                raise
            
            # Clear in-progress flag
            close_old_connections()
            try:
                cache.delete('update_in_progress')
            except Exception as cache_err:
                logger.error(f"Cache error during cleanup: {cache_err}")
            
        except Exception as e:
            logger.error(f"Update failed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            try:
                close_old_connections()
                cache.delete('update_in_progress')
                cache.set('last_scraping_error', traceback.format_exc()[:1000], timeout=86400)
            except Exception as cache_err:
                logger.error(f"Failed to clean up after error: {cache_err}")
        finally:
            try:
                close_old_connections()
            except:
                pass
    
    # Start update in background thread
    try:
        thread = threading.Thread(target=run_update, daemon=True)
        thread.start()
        logger.info(f"✅ Background thread started successfully (Thread ID: {thread.ident})")
    except Exception as thread_error:
        logger.error(f"Failed to start background thread: {thread_error}")
        try:
            cache.delete('update_in_progress')
        except:
            pass
        return Response({
            "status": "error",
            "message": "Failed to start background update",
            "error": str(thread_error)
        }, status=500)
    
    return Response({
        "status": "started",
        "message": "✅ Product update started in background",
        "timestamp": timezone.now().isoformat(),
        "note": "Check GET /api/update/ for status",
        "help": "If this consistently fails, check logs or run: python manage.py populate_catalog"
    }, status=202)  # 202 Accepted - processing started


@api_view(['POST', 'GET'])
@permission_classes([permissions.AllowAny])
@throttle_classes([ScrapingRateThrottle])
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
@permission_classes([permissions.AllowAny])
@throttle_classes([ScrapingRateThrottle])
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
    is_production = os.environ.get('RENDER', False) or not settings.DEBUG
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
@permission_classes([permissions.AllowAny])
@throttle_classes([ScrapingRateThrottle])
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


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def reset_scraping_lock(request):
    """
    Emergency endpoint to clear stuck scraping cache locks
    POST /api/reset-scraping-lock/
    """
    from django.core.cache import cache
    
    try:
        cache.delete('update_in_progress')
        cache.delete('catalog_update_in_progress')
        cache.delete('cleanup_in_progress')
        cache.delete('product_cleanup_in_progress')
        
        return Response({
            "status": "success",
            "message": "✅ All scraping locks cleared",
            "cleared_locks": [
                "update_in_progress",
                "catalog_update_in_progress", 
                "cleanup_in_progress",
                "product_cleanup_in_progress"
            ]
        }, status=200)
    except Exception as e:
        return Response({
            "status": "error",
            "message": f"Failed to clear locks: {str(e)}"
        }, status=500)


# ========================================
# POPULAR PRODUCTS API
# ========================================

TARGET_CATEGORIES = [
    'Mouse', 'Keyboard', 'Processor', 'GPU', 'RAM', 'Monitor',
    'Motherboard', 'SSD', 'HDD', 'Power Supply', 'Cabinet', 'CPU Cooler',
]


@swagger_auto_schema(
    method='get',
    operation_description=(
        "Returns one randomly selected product from each major category "
        "(Mouse, Keyboard, Processor, GPU, RAM, Monitor, Motherboard, SSD, "
        "HDD, Power Supply, Cabinet, CPU Cooler). "
        "Only products with an image and a positive price are included. "
        "Random selection is performed at the database level for performance."
    ),
    responses={
        200: openapi.Response(
            description="List of popular products (one per category, up to 12)",
            schema=openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id':            openapi.Schema(type=openapi.TYPE_INTEGER),
                        'name':          openapi.Schema(type=openapi.TYPE_STRING),
                        'category_name': openapi.Schema(type=openapi.TYPE_STRING),
                        'category_slug': openapi.Schema(type=openapi.TYPE_STRING),
                        'current_price': openapi.Schema(type=openapi.TYPE_NUMBER),
                        'image_url':     openapi.Schema(type=openapi.TYPE_STRING),
                        'shop_name':     openapi.Schema(type=openapi.TYPE_STRING),
                    },
                ),
            ),
        ),
    },
)
@api_view(['GET'])
def popular_products(request):
    """
    GET /api/popular-products/

    Returns one randomly selected product per major category using a single
    database-level random query (DISTINCT ON for PostgreSQL, window function
    for SQLite).  Only products that have both an image_url and a positive
    current_price are eligible.
    """
    from django.db import connection
    from django.conf import settings

    engine = settings.DATABASES['default']['ENGINE']
    is_postgres = 'postgresql' in engine or 'psycopg' in engine

    placeholders = ', '.join(['%s'] * len(TARGET_CATEGORIES))

    if is_postgres:
        # PostgreSQL: DISTINCT ON keeps the first row per category_id after
        # ORDER BY category_id, RANDOM() – a single fast index scan.
        sql = f"""
            SELECT DISTINCT ON (p.category_id)
                p.id,
                p.name,
                p.current_price,
                p.image_url,
                c.name  AS category_name,
                c.slug  AS category_slug,
                s.name  AS shop_name
            FROM   products_product  p
            INNER JOIN products_category c ON c.id = p.category_id
            INNER JOIN products_shop     s ON s.id = p.shop_id
            WHERE  p.image_url    IS NOT NULL
              AND  p.image_url    != ''
              AND  p.current_price > 0
              AND  c.name IN ({placeholders})
            ORDER BY p.category_id, RANDOM()
            LIMIT 12
        """
    else:
        # SQLite 3.25+ supports window functions.
        # ROW_NUMBER() OVER (PARTITION BY category_id ORDER BY RANDOM())
        # gives each product a rank within its category; keeping rank = 1
        # picks exactly one random product per category.
        sql = f"""
            SELECT id, name, current_price, image_url,
                   category_name, category_slug, shop_name
            FROM (
                SELECT
                    p.id,
                    p.name,
                    p.current_price,
                    p.image_url,
                    c.name  AS category_name,
                    c.slug  AS category_slug,
                    s.name  AS shop_name,
                    ROW_NUMBER() OVER (
                        PARTITION BY p.category_id
                        ORDER BY RANDOM()
                    ) AS rn
                FROM   products_product  p
                INNER JOIN products_category c ON c.id = p.category_id
                INNER JOIN products_shop     s ON s.id = p.shop_id
                WHERE  p.image_url    IS NOT NULL
                  AND  p.image_url    != ''
                  AND  p.current_price > 0
                  AND  c.name IN ({placeholders})
            ) ranked
            WHERE rn = 1
            LIMIT 12
        """

    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, TARGET_CATEGORIES)
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

        products_data = [
            dict(zip(columns, row))
            for row in rows
        ]

        serializer = PopularProductSerializer(products_data, many=True)
        return Response(serializer.data)

    except Exception as exc:
        logger.error(f"popular_products query failed: {exc}")
        return Response(
            {"error": "Failed to fetch popular products."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['POST'])
def run_migrations(request):
    """
    Run database migrations via API
    POST /api/migrate/ - Run pending migrations
    """
    from django.core.management import call_command
    from io import StringIO
    import sys
    
    try:
        # Capture migration output
        output = StringIO()
        call_command('migrate', '--noinput', stdout=output, stderr=output)
        
        migration_output = output.getvalue()
        
        return Response({
            "status": "success",
            "message": "Migrations completed successfully",
            "output": migration_output,
            "timestamp": timezone.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        return Response({
            "status": "error",
            "message": f"Migration failed: {str(e)}",
            "timestamp": timezone.now().isoformat()
        }, status=500)


# ========================================
# WISHLIST API
# ========================================

@swagger_auto_schema(
    method='post',
    request_body=StockSubscriptionInputSerializer,
    responses={
        201: openapi.Response(description='Subscription created'),
        400: 'Invalid payload, duplicate subscription, or product is already in stock',
        401: 'Unauthorized',
        404: 'Product not found',
    },
    operation_description='Subscribe the authenticated user to a back-in-stock alert for an out-of-stock product',
    operation_id='stock_subscription_create',
    tags=['Stock Notifications']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def subscribe_to_stock_notification(request):
    serializer = StockSubscriptionInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    product_id = serializer.validated_data['product_id']
    product = Product.objects.select_related('shop').filter(id=product_id).first()
    if not product:
        return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

    if product.stock_status != 'out_of_stock' or product.is_available:
        return Response(
            {'error': 'Stock notifications are only available for out-of-stock products.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    subscription, created = StockSubscription.objects.get_or_create(
        user=request.user,
        product=product,
    )

    if not created:
        return Response(
            {'error': 'You are already subscribed to this product.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            'message': 'Subscription created successfully.',
            'subscription': StockSubscriptionSerializer(subscription, context={'request': request}).data,
        },
        status=status.HTTP_201_CREATED,
    )


@swagger_auto_schema(
    method='delete',
    request_body=StockSubscriptionInputSerializer,
    responses={
        200: openapi.Response(description='Subscription removed'),
        400: 'Invalid payload',
        401: 'Unauthorized',
        404: 'Subscription not found',
    },
    operation_description='Unsubscribe the authenticated user from a back-in-stock alert for a product',
    operation_id='stock_subscription_remove',
    tags=['Stock Notifications']
)
@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def unsubscribe_from_stock_notification(request):
    serializer = StockSubscriptionInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    product_id = serializer.validated_data['product_id']
    deleted_count, _ = StockSubscription.objects.filter(
        user=request.user,
        product_id=product_id,
    ).delete()

    if deleted_count == 0:
        product_exists = Product.objects.filter(id=product_id).exists()
        if not product_exists:
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'error': 'Subscription not found.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(
        {'message': 'Subscription removed successfully.'},
        status=status.HTTP_200_OK,
    )

@swagger_auto_schema(
    method='post',
    request_body=WishlistInputSerializer,
    responses={
        201: openapi.Response(description='Product added to wishlist'),
        400: 'Invalid payload or duplicate wishlist item',
        401: 'Unauthorized',
        404: 'Product not found',
    },
    operation_description='Add a product to the authenticated user wishlist',
    operation_id='wishlist_add',
    tags=['Wishlist']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def add_to_wishlist(request):
    serializer = WishlistInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    product_id = serializer.validated_data['product_id']
    product = Product.objects.filter(id=product_id).first()
    if not product:
        return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

    wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if not created:
        return Response(
            {'error': 'Product is already in your wishlist.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            'message': 'Product added to wishlist.',
            'item': WishlistItemSerializer(wishlist_item, context={'request': request}).data,
        },
        status=status.HTTP_201_CREATED,
    )


@swagger_auto_schema(
    method='get',
    responses={
        200: WishlistItemSerializer(many=True),
        401: 'Unauthorized',
    },
    operation_description='Get wishlist items for the authenticated user',
    operation_id='wishlist_list',
    tags=['Wishlist']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_user_wishlist(request):
    queryset = Wishlist.objects.filter(user=request.user).select_related(
        'product', 'product__category', 'product__shop'
    )
    items = WishlistItemSerializer(queryset, many=True, context={'request': request})
    return Response({'count': len(items.data), 'results': items.data}, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='delete',
    request_body=WishlistInputSerializer,
    responses={
        200: openapi.Response(description='Product removed from wishlist'),
        400: 'Invalid payload',
        401: 'Unauthorized',
        404: 'Product not found in wishlist',
    },
    operation_description='Remove a product from the authenticated user wishlist',
    operation_id='wishlist_remove',
    tags=['Wishlist']
)
@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def remove_from_wishlist(request):
    serializer = WishlistInputSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    product_id = serializer.validated_data['product_id']
    deleted_count, _ = Wishlist.objects.filter(user=request.user, product_id=product_id).delete()

    if deleted_count == 0:
        product_exists = Product.objects.filter(id=product_id).exists()
        if not product_exists:
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'error': 'Product is not in your wishlist.'}, status=status.HTTP_404_NOT_FOUND)

    return Response({'message': 'Product removed from wishlist.'}, status=status.HTTP_200_OK)