from rest_framework.decorators import api_view
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .cache_manager import price_cache
from .scraper import (
    scrape_startech, scrape_ryans, scrape_skyland,
    scrape_pchouse, scrape_ultratech, scrape_binary_playwright, scrape_potakait
)

import asyncio
import logging
import time
import os
from playwright.async_api import async_playwright
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("products.views")

# Detect environment and set adaptive timeouts
IS_CLOUD = os.environ.get('RENDER') or os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('HEROKU_APP_NAME')
PLAYWRIGHT_TIMEOUT = 15000 if IS_CLOUD else 8000  # 15s on cloud, 8s locally
HTTP_TIMEOUT = 12 if IS_CLOUD else 8  # 12s on cloud, 8s locally  
SCRAPER_TIMEOUT = 30 if IS_CLOUD else 15  # 30s on cloud (for individual browsers), 15s locally

# Debug logging
logger.info(f"Environment: {'CLOUD' if IS_CLOUD else 'LOCAL'} | Playwright: {PLAYWRIGHT_TIMEOUT}ms | HTTP: {HTTP_TIMEOUT}s | Scraper: {SCRAPER_TIMEOUT}s")

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
    
    start_time = time.time()
    logger.info(f"=== Request started ===")
    
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
        total_time = (time.time() - start_time) * 1000
        logger.info(f"Cache hit for '{product}' - Total time: {total_time:.2f}ms")
        return Response(cached_result)
    
    # Clean up expired cache 
    price_cache.clear_expired()
    
    cache_check_time = time.time()
    logger.info(f"Cache check completed: {(cache_check_time - start_time) * 1000:.2f}ms")
    
    async def gather_dynamic(product):
        # Each scraper now uses individual browser instances for reliability
        tasks = [
            scrape_ryans(product),
            scrape_binary_playwright(product)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions gracefully  
        ryans = results[0] if not isinstance(results[0], Exception) else {"products": [], "logo": ""}
        binary = results[1] if not isinstance(results[1], Exception) else {"products": [], "logo": ""}

        return ryans, binary    # run static scrapers with timeout and resource optimization
    async def run_static_scrapers_async(product):
        def run_static_scrapers(product):
            with ThreadPoolExecutor(max_workers=3) as executor:  # Reduced workers for cloud
                tasks = [
                    executor.submit(scrape_startech, product),
                    executor.submit(scrape_skyland, product),
                    executor.submit(scrape_pchouse, product),
                    executor.submit(scrape_ultratech, product),
                    executor.submit(scrape_potakait, product),
                ]
                results = []
                scraper_names = ['startech', 'skyland', 'pchouse', 'ultratech', 'potakait']
                for i, task in enumerate(tasks):
                    try:
                        # Adaptive timeout per scraper (15s cloud, 8s local)
                        result = task.result(timeout=SCRAPER_TIMEOUT)
                        results.append(result)
                        logger.info(f"✅ {scraper_names[i]} scraper completed successfully")
                    except Exception as e:
                        logger.warning(f"❌ {scraper_names[i]} scraper failed: {type(e).__name__}: {e}")
                        results.append({"products": [], "logo": ""})
                return results
        
        # Run static scrapers in executor to make them async
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, run_static_scrapers, product)

    # Run both dynamic and static scrapers in parallel
    async def run_all_scrapers():
        parallel_start = time.time()
        
        # Start both tasks
        dynamic_start = time.time()
        dynamic_task = gather_dynamic(product)
        static_start = time.time()
        static_task = run_static_scrapers_async(product)
        
        # Wait for both to complete simultaneously
        (ryans, binary), static_results = await asyncio.gather(dynamic_task, static_task, return_exceptions=True)
        
        # Handle exceptions
        if isinstance((ryans, binary), Exception):
            logger.error(f"Dynamic scrapers failed: {ryans, binary}")
            ryans, binary = {"products": [], "logo": ""}, {"products": [], "logo": ""}
        
        if isinstance(static_results, Exception):
            logger.error(f"Static scrapers failed: {static_results}")
            static_results = [{"products": [], "logo": ""} for _ in range(5)]
            
        startech, skyland, pchouse, ultratech, potakait = static_results
        
        parallel_end = time.time()
        logger.info(f"All scrapers completed in parallel: {(parallel_end - parallel_start) * 1000:.2f}ms")
        
        return ryans, binary, startech, skyland, pchouse, ultratech, potakait
    
    # Execute all scrapers in parallel with optimized browser pool
    try:
        logger.info("🚀 Using optimized parallel execution with individual browsers")
        ryans, binary, startech, skyland, pchouse, ultratech, potakait = asyncio.run(run_all_scrapers())
    except Exception as e:
        logger.error(f"Scraper execution failed: {e}")
        # Return empty results as fallback
        ryans = binary = startech = skyland = pchouse = ultratech = potakait = {"products": [], "logo": ""}
    
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
    
    total_time = (time.time() - start_time) * 1000
    logger.info(f"=== REQUEST COMPLETED ===")
    logger.info(f"Product: '{product}' - Found {len(shops_with_results)} shops")
    logger.info(f"Total request time: {total_time:.2f}ms")
    logger.info(f"=========================")
    
    return Response(shops_with_results)