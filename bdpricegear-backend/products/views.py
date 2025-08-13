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
    
    try:
        startech, ryans = asyncio.run(gather_dynamic())
    except Exception as e:
        logger.error(f"Error running dynamic scrapers: {e}")
        startech, ryans = {"products": [], "logo": ""}, {"products": [], "logo": ""}