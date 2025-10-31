from celery import shared_task
from django.utils import timezone
from django.db import transaction
import logging
import asyncio
from playwright.async_api import async_playwright
from concurrent.futures import ThreadPoolExecutor

from .models import Product, Shop, Category, PriceHistory
from .utils.scraper import (
    scrape_startech, scrape_ryans, scrape_skyland,
    scrape_pchouse, scrape_ultratech, scrape_binary_playwright, scrape_potakait
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='products.tasks.scrape_all_shops')
def scrape_all_shops(self):
    # 
    # Main task to scrape all shops and save to database.
    # Runs every hour via Celery Beat.
    # 
    logger.info("Starting scheduled scraping for all shops...")
    
    try:
        # Get all active shops
        shops = Shop.objects.filter(is_active=True, scraping_enabled=True)
        
        if not shops.exists():
            logger.warning("No active shops found for scraping")
            return {"status": "skipped", "message": "No active shops"}
        
        # Get all categories to search for
        categories = Category.objects.filter(is_active=True)
        search_terms = [cat.name.lower() for cat in categories]
        
        if not search_terms:
            # Default search terms if no categories
            search_terms = ['laptop', 'mouse', 'keyboard', 'monitor']
        
        total_products = 0
        total_updated = 0
        total_created = 0
        
        # Scrape each search term
        for term in search_terms:
            logger.info(f"Scraping for: {term}")
            
            # Run scrapers
            scraped_data = run_all_scrapers(term)
            
            # Save to database
            created, updated = save_scraped_products(scraped_data, term)
            total_created += created
            total_updated += updated
            total_products += (created + updated)
        
        logger.info(f"Scraping completed: {total_created} created, {total_updated} updated")
        
        return {
            "status": "success",
            "total_products": total_products,
            "created": total_created,
            "updated": total_updated,
            "timestamp": timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in scraping task: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "timestamp": timezone.now().isoformat()
        }


def run_all_scrapers(search_term):
    # Run all scrapers for a given search term
    
    async def gather_all_scrapers(product):
        # Dynamic scrapers (Playwright)
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

        # Static scrapers (BeautifulSoup)
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

        # Run both in parallel
        loop = asyncio.get_event_loop()
        dynamic_task = run_dynamic()
        static_task = loop.run_in_executor(None, run_static)
        
        dynamic_results, static_results = await asyncio.gather(dynamic_task, static_task)
        
        ryans, binary = dynamic_results
        startech, skyland, pchouse, ultratech, potakait = static_results
        
        return {
            'StarTech': startech,
            'Ryans': ryans,
            'SkyLand': skyland,
            'PcHouse': pchouse,
            'UltraTech': ultratech,
            'Binary': binary,
            'PotakaIT': potakait,
        }

    return asyncio.run(gather_all_scrapers(search_term))


@transaction.atomic
def save_scraped_products(scraped_data, search_term):

    # Save scraped products to database
    # Returns: (created_count, updated_count)
    
    created_count = 0
    updated_count = 0
    
    # Try to find matching category
    category = Category.objects.filter(name__iexact=search_term).first()
    
    for shop_name, shop_data in scraped_data.items():
        # Get or create shop
        shop, _ = Shop.objects.get_or_create(
            name=shop_name,
            defaults={
                'website_url': 'https://example.com',  # You can improve this
                'logo_url': shop_data.get('logo', ''),
            }
        )
        
        # Update logo if available
        if shop_data.get('logo') and not shop.logo_url:
            shop.logo_url = shop_data['logo']
            shop.save()
        
        # Process products
        for product_data in shop_data.get('products', []):
            # Skip if no valid price
            price = product_data.get('price')
            if isinstance(price, str) or price == 0:
                continue
            
            product_url = product_data.get('link', '')
            if not product_url or product_url == '#' or product_url == 'Link not found':
                continue
            
            # Check if product exists
            product, created = Product.objects.update_or_create(
                shop=shop,
                product_url=product_url,
                defaults={
                    'name': product_data.get('name', 'Unknown Product')[:500],
                    'category': category,
                    'image_url': product_data.get('img', ''),
                    'current_price': price,
                    'stock_status': 'in_stock' if product_data.get('in_stock', True) else 'out_of_stock',
                    'is_available': True,
                    'last_scraped': timezone.now(),
                }
            )
            
            if created:
                created_count += 1
                logger.info(f"Created new product: {product.name}")
            else:
                updated_count += 1
            
            # Record price history (only if price changed)
            latest_history = product.price_history.first()
            if not latest_history or latest_history.price != product.current_price:
                PriceHistory.objects.create(
                    product=product,
                    price=product.current_price,
                    stock_status=product.stock_status,
                    recorded_at=timezone.now()
                )
    
    return created_count, updated_count
