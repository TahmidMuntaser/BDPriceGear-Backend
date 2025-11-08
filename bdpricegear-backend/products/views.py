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
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent="Mozilla/5.0")

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
    
    queryset = Product.objects.filter(is_available=True).select_related('category', 'shop')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'brand', 'description']
    ordering_fields = ['current_price', 'created_at', 'discount_percentage', 'name']
    ordering = ['-created_at']
    
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
   
    # Health check endpoint for UptimeRobot monitoring.
    # Also prevents Render from sleeping.
    # Returns database and Celery status.
    
    from django.db import connection
    from django.core.cache import cache
    import redis
    
    database_status = "disconnected"
    redis_status = "disconnected"
    product_count = 0
    
    try:
        # Check database
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM products_product")
            product_count = cursor.fetchone()[0]
        database_status = "connected"
    except Exception as e:
        database_status = f"error: {str(e)}"
    
    try:
        # Check Redis/Celery
        from celery import current_app
        result = current_app.control.inspect().active()
        redis_status = "connected" if result else "no_workers"
    except Exception as e:
        redis_status = f"error: {str(e)}"
    
    return Response({
        "status": "ok",
        "timestamp": timezone.now().isoformat(),
        "service": "BDPriceGear Backend",
        "database": database_status,
        "redis": redis_status,
        "products_in_db": product_count,
        "celery_workers_active": redis_status == "connected"
    })
