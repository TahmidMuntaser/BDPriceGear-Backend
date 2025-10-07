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
    
    async def gather_dynamic(product):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--disable-dev-shm-usage', '--no-sandbox', '--disable-gpu']
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )

            tasks = [
                scrape_ryans(product, context),
                scrape_binary_playwright(product, context) 
            ]
            results = await asyncio.gather(*tasks)
            ryans, binary = results

            await browser.close()
            return ryans, binary

    ryans, binary = asyncio.run(gather_dynamic(product))

    # run static scrapers with balanced timeout for cloud deployment
    def run_static_scrapers(product):
        with ThreadPoolExecutor(max_workers=5) as executor:
            tasks = [
                executor.submit(scrape_startech, product),
                executor.submit(scrape_skyland, product),
                executor.submit(scrape_pchouse, product),
                executor.submit(scrape_ultratech, product),
                executor.submit(scrape_potakait, product),
            ]
            results = []
            for task in tasks:
                try:
                    results.append(task.result(timeout=6))  # 6 second timeout per scraper (balanced)
                except Exception as e:
                    logger.warning(f"Static scraper timeout/failed: {e}")
                    results.append({"products": [], "logo": "logo not found"})
            return results

    startech, skyland, pchouse, ultratech, potakait = run_static_scrapers(product)
    
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
    
    # Cache the results: 10 min
    price_cache.set(product, shops_with_results, ttl=600)
    logger.info(f"Cached results for '{product}' - Found {len(shops_with_results)} shops")
    
    return Response(shops_with_results)