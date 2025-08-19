from rest_framework.decorators import api_view
from rest_framework.response import Response
from .scraper import (
    scrape_startech, scrape_ryans, scrape_techland, scrape_skyland,
    scrape_pchouse, scrape_ultratech, scrape_binary, scrape_potakait
)

import asyncio
import logging
from playwright.async_api import async_playwright
from concurrent.futures import ThreadPoolExecutor 

logger = logging.getLogger("products.views")

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
                executor.submit(scrape_techland, product),
                executor.submit(scrape_skyland, product),
                executor.submit(scrape_pchouse, product),
                executor.submit(scrape_ultratech, product),
                executor.submit(scrape_binary, product),
                executor.submit(scrape_potakait, product),
            ]
            return [task.result() for task in tasks]
        
    startech, techland, skyland, pchouse, ultratech, binary, potakait = run_static_scrapers(product)
    
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
        {"name": "TechLand", **techland},
        {"name": "SkyLand", **skyland},
        {"name": "PcHouse", **pchouse},
        {"name": "UltraTech", **ultratech},
        {"name": "Binary", **binary},
        {"name": "PotakaIT", **potakait},
    ]
    
    # filter empty results 
    shops_with_results = [shop for shop in all_shops if shop.get("products")]
    
    return Response(shops_with_results)
    