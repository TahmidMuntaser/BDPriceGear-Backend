from rest_framework.decorators import api_view
from rest_framework.response import Response
from .scraper import (
    scrape_startech, scrape_ryans, scrape_techland, scrape_skyland,
    scrape_pchouse, scrape_ultratech, scrape_binary, scrape_potakait
)

import asyncio
import logging

logger = logging.getLogger("products.views")

@api_view(['GET'])
def price_comparison(request):
    
    product = request.GET.get('product')
    # placeholder endpoint
    if not product:
        return Response({"error": "Missing 'product' query parameter"}, status=400)
    
    async def gather_dynamic(product):
        startech = await scrape_startech(product)
        ryans = await scrape_ryans(product)
        
        return startech, ryans
    
    # run dynamic scrapers
    # try:
    #     startech, ryans = asyncio.run(gather_dynamic())
    # except Exception as e:
    #     logger.error(f"Error running dynamic scrapers: {e}")
    #     startech, ryans = {"products": [], "logo": ""}, {"products": [], "logo": ""}
        
        
    startech, ryans = asyncio.run(gather_dynamic(product))
    # run static scrapers
    techland = scrape_techland(product)
    skyland = scrape_skyland(product)
    pchouse = scrape_pchouse(product)
    ultratech = scrape_ultratech(product)
    binary = scrape_binary(product)
    potakait = scrape_potakait(product)
    
    # combine scraper results
    all_shops = [
        {"name": "StarTech", **startech},
        {"name": "Ryans", **ryans},
        {"name": "TechLand", **techland},
        {"name": "SkyLand", **skyland},
        {"name": "Ryans", **ryans},
        {"name": "PcHouse", **pchouse},
        {"name": "UltraTech", **ultratech},
        {"name": "Binary", **binary},
        {"name": "PotakaIT", **potakait},
    ]
    
    # filter empty results 
    shops_with_results = [shop for shop in all_shops if shop.get("products")]
    
    return Response(shops_with_results)
    