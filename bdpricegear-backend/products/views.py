from rest_framework.decorators import api_view
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .scraper import (
    scrape_startech, scrape_ryans, scrape_skyland,
    scrape_pchouse, scrape_ultratech, scrape_binary, scrape_potakait
)

import asyncio
import logging
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

@api_view(['GET', 'HEAD'])
def price_comparison(request):
    
    product = request.GET.get('product')
    # placeholder endpoint
    if not product:
        return Response({"error": "Missing 'product' query parameter"}, status=400)
    
    async def gather_dynamic(product):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent="Mozilla/5.0")

            tasks = [scrape_ryans(product, context)]
            results = await asyncio.gather(*tasks)
            ryans = results[0]

            await browser.close()
            return ryans

    ryans = asyncio.run(gather_dynamic(product))

    # run static scrapers
    
    def run_static_scrapers(product):
        with ThreadPoolExecutor() as executor:
            tasks = [
                executor.submit(scrape_startech, product),
                # executor.submit(scrape_techland, product),
                executor.submit(scrape_skyland, product),
                executor.submit(scrape_pchouse, product),
                executor.submit(scrape_ultratech, product),
                # executor.submit(scrape_binary, product),  # Disabled: blocked on cloud servers
                executor.submit(scrape_potakait, product),
            ]
            return [task.result() for task in tasks]
        
    startech, skyland, pchouse, ultratech, potakait = run_static_scrapers(product)
    
    # Create empty result for binary to maintain structure
    binary = {"products": [], "logo": "https://www.binarylogic.com.bd/images/logo.png"}
    
    # techland = scrape_techland(product)
    # skyland = scrape_skyland(product)
    # pchouse = scrape_pchouse(product)
    # ultratech = scrape_ultratech(product)
    # binary = scrape_binary(product)
    # potakait = scrape_potakait(product)
    
    # combine scraper results
    all_shops = [
        {"name": "StarTech", **startech},
        {"name": "Ryans", **ryans},
        # {"name": "TechLand", **techland},
        {"name": "SkyLand", **skyland},
        {"name": "PcHouse", **pchouse},
        {"name": "UltraTech", **ultratech},
        {"name": "Binary", **binary},
        {"name": "PotakaIT", **potakait},
    ]
    
    # filter empty results 
    shops_with_results = [shop for shop in all_shops if shop.get("products")]
    
    return Response(shops_with_results)
    