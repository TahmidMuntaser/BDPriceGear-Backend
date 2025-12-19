
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
import asyncio
import logging
from playwright.async_api import async_playwright
from concurrent.futures import ThreadPoolExecutor
import queue
import threading

logger = logging.getLogger(__name__)

from products.models import Product, Shop, Category, PriceHistory
from products.utils.catalog_scraper import (
    scrape_startech_catalog, scrape_skyland_catalog, scrape_pchouse_catalog,
    scrape_ultratech_catalog, scrape_potakait_catalog,
    scrape_ryans_catalog, scrape_binary_catalog
)


class Command(BaseCommand):
    help = 'Populate catalog database with all products from all pages (no duplicate removal)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--categories',
            nargs='+',
            type=str,
            default=['laptop', 'mouse', 'keyboard', 'monitor', 'webcam', 'microphone', 'speaker', 'headphone', 'ram', 'ssd', 'hdd'],
            help='Categories to scrape'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting catalog population...'))
        
        categories_created = self.create_categories(options['categories'])
        self.stdout.write(self.style.SUCCESS(f'Categories ready: {categories_created}'))
        
        shops_created = self.create_shops()
        self.stdout.write(self.style.SUCCESS(f'Shops ready: {shops_created}'))
        
        total_created = 0
        total_updated = 0
        
        for category in options['categories']:
            self.stdout.write(f'\nScraping category: {category}')
            
            # Queue for passing scraped data from scraper to saver
            data_queue = queue.Queue()
            save_thread = None
            
            def save_worker():
                nonlocal total_created, total_updated
                while True:
                    item = data_queue.get()
                    if item is None:  # Sentinel to stop
                        break
                    shop_name, shop_data = item
                    created, updated = self.save_shop_products(shop_name, shop_data, category)
                    total_created += created
                    total_updated += updated
                    data_queue.task_done()
            
            # Start save worker thread
            save_thread = threading.Thread(target=save_worker, daemon=True)
            save_thread.start()
            
            # Run scrapers and feed queue
            scraped_data = self.run_catalog_scrapers_streaming(category, data_queue)
            
            # Wait for all saves to complete
            data_queue.join()
            data_queue.put(None)  # Stop signal
            save_thread.join()
        
        self.stdout.write(self.style.SUCCESS(f'\nCatalog populated: {total_created} products created, {total_updated} updated'))

    def create_categories(self, category_names):
        count = 0
        categories = ['Laptop', 'Mouse', 'Keyboard', 'Monitor', 'Headphone', 'Speaker', 'Webcam', 'Microphone', 'RAM', 'SSD', 'HDD']
        
        for cat_name in categories:
            _, created = Category.objects.update_or_create(
                name=cat_name,
                defaults={'is_active': True}
            )
            if created:
                count += 1
        
        return count

    def create_shops(self):
        count = 0
        shops = [
            {'name': 'StarTech', 'website_url': 'https://www.startech.com.bd', 'logo_url': 'https://www.startech.com.bd/catalog/view/theme/starship/images/logo.png', 'priority': 5},
            {'name': 'Ryans', 'website_url': 'https://www.ryans.com', 'logo_url': 'https://www.ryans.com/wp-content/themes/ryans/img/logo.png', 'priority': 4},
            {'name': 'SkyLand', 'website_url': 'https://www.skyland.com.bd', 'logo_url': 'https://www.skyland.com.bd/image/catalog/logo.png', 'priority': 3},
            {'name': 'PcHouse', 'website_url': 'https://www.pchouse.com.bd', 'logo_url': 'https://www.pchouse.com.bd/image/catalog/unnamed.png', 'priority': 3},
            {'name': 'UltraTech', 'website_url': 'https://www.ultratech.com.bd', 'logo_url': 'https://www.ultratech.com.bd/image/catalog/logo.png', 'priority': 2},
            {'name': 'Binary', 'website_url': 'https://www.binarylogic.com.bd', 'logo_url': 'https://www.binarylogic.com.bd/images/logo.png', 'priority': 2},
            {'name': 'PotakaIT', 'website_url': 'https://www.potakait.com', 'logo_url': 'https://www.potakait.com/image/catalog/logo.png', 'priority': 1},
        ]
        
        for shop_data in shops:
            _, created = Shop.objects.get_or_create(
                name=shop_data['name'],
                defaults={
                    'website_url': shop_data['website_url'],
                    'logo_url': shop_data['logo_url'],
                    'priority': shop_data['priority'],
                    'is_active': True,
                    'scraping_enabled': True
                }
            )
            if created:
                count += 1
        
        return count

    def run_catalog_scrapers_streaming(self, category, data_queue):
        """Run scrapers and stream results to queue as they complete"""
        async def gather_scrapers_streaming(cat, queue):
            async def run_dynamic():
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context(user_agent="Mozilla/5.0")

                    try:
                        # Run Ryans
                        ryans_result = await asyncio.wait_for(scrape_ryans_catalog(cat, context), timeout=300)
                        queue.put(('Ryans', ryans_result))
                        
                        # Run Binary
                        binary_result = await asyncio.wait_for(scrape_binary_catalog(cat, context), timeout=300)
                        queue.put(('Binary', binary_result))
                    except asyncio.TimeoutError:
                        logger.warning(f"Dynamic scrapers timed out for {cat}")
                    finally:
                        await browser.close()

            def run_static_streaming():
                scrapers = [
                    ('StarTech', scrape_startech_catalog),
                    ('SkyLand', scrape_skyland_catalog),
                    ('PcHouse', scrape_pchouse_catalog),
                    ('UltraTech', scrape_ultratech_catalog),
                    ('PotakaIT', scrape_potakait_catalog),
                ]
                
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = {executor.submit(scraper, cat): name for name, scraper in scrapers}
                    
                    for future in futures:
                        try:
                            result = future.result()
                            shop_name = futures[future]
                            queue.put((shop_name, result))
                        except Exception as e:
                            logger.error(f"Error scraping {futures[future]}: {e}")

            loop = asyncio.get_event_loop()
            dynamic_task = run_dynamic()
            static_task = loop.run_in_executor(None, run_static_streaming)
            
            await asyncio.gather(dynamic_task, static_task)

        asyncio.run(gather_scrapers_streaming(category, data_queue))

    @transaction.atomic
    def save_shop_products(self, shop_name, shop_data, category_name):
        """Save products from a single shop"""
        created_count = 0
        updated_count = 0
        
        self.stdout.write(f'  Saving {shop_name} products...')
        
        category = Category.objects.filter(name__iexact=category_name).first()
        price_histories_to_create = []
        
        try:
            shop = Shop.objects.get(name=shop_name)
        except Shop.DoesNotExist:
            return 0, 0
        
        if shop_data.get('logo') and not shop.logo_url:
            shop.logo_url = shop_data['logo']
            shop.save()
        
        products = shop_data.get('products', [])
        batch_size = 100
        
        for i in range(0, len(products), batch_size):
            batch = products[i:i + batch_size]
            
            for product_data in batch:
                price = product_data.get('price')
                product_url = product_data.get('link', '')
                
                if not product_url or product_url in ['#', 'Link not found', '']:
                    continue
                
                if isinstance(price, str) or price == 0 or price is None:
                    stock_status = 'out_of_stock'
                    is_available = False
                    current_price = 0
                else:
                    stock_status = 'in_stock' if product_data.get('in_stock', True) else 'out_of_stock'
                    is_available = True
                    current_price = price
                
                product, created = Product.objects.update_or_create(
                    shop=shop,
                    product_url=product_url,
                    defaults={
                        'name': product_data.get('name', 'Unknown Product')[:500],
                        'category': category,
                        'image_url': product_data.get('img', ''),
                        'current_price': current_price,
                        'stock_status': stock_status,
                        'is_available': is_available,
                        'last_scraped': timezone.now(),
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                
                # Batch price history creation
                latest_history = product.price_history.first()
                if not latest_history or latest_history.price != product.current_price:
                    price_histories_to_create.append(
                        PriceHistory(
                            product=product,
                            price=product.current_price,
                            stock_status=product.stock_status,
                            recorded_at=timezone.now()
                        )
                    )
            
            # Bulk create price histories every batch
            if price_histories_to_create:
                PriceHistory.objects.bulk_create(price_histories_to_create, batch_size=100)
                price_histories_to_create = []
        
        # Create remaining price histories
        if price_histories_to_create:
            PriceHistory.objects.bulk_create(price_histories_to_create, batch_size=100)
        
        self.stdout.write(f'    {shop_name}: {created_count} created, {updated_count} updated')
        return created_count, updated_count

