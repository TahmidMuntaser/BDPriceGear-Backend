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
    
    