from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction, close_old_connections
import asyncio
import logging
import urllib.parse
from playwright.async_api import async_playwright
from concurrent.futures import ThreadPoolExecutor
import queue
import threading

logger = logging.getLogger(__name__)

from products.models import Product, Shop, Category, PriceHistory
from products.utils.catalog_scraper import (
    scrape_startech_catalog, scrape_skyland_catalog, scrape_pchouse_catalog,
    scrape_ultratech_catalog, scrape_potakait_catalog,
    scrape_ryans_catalog, scrape_binary_catalog, normalize_product_url
)


class Command(BaseCommand):
    help = 'Populate catalog database with all products from all pages (no duplicate removal)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--categories',
            nargs='+',
            type=str,
            default=['Processor', 'Motherboard', 'RAM', 'SSD', 'HDD', 'Power Supply', 'Cabinet', 'GPU', 'CPU Cooler', 'Monitor', 'Keyboard', 'Mouse'],
            help='PC component categories to scrape'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting catalog population...'))

        # Map category names to search terms for websites
        category_to_search_term = {
            'Processor': 'CPU',
            'Motherboard': 'Motherboard',
            'RAM': 'RAM',
            'SSD': 'SSD',
            'HDD': 'HDD',
            'Power Supply': 'Power Supply',
            'Cabinet': 'PC Case',
            'GPU': 'Graphics Card',
            'CPU Cooler': 'CPU Cooler',
            'Monitor': 'Monitor',
            'Keyboard': 'Keyboard',
            'Mouse': 'Mouse',
        }

        categories_created = self.create_categories(options['categories'])
        self.stdout.write(self.style.SUCCESS(f'Categories ready: {categories_created}'))

        shops_created = self.create_shops()
        self.stdout.write(self.style.SUCCESS(f'Shops ready: {shops_created}'))

        total_created = 0
        total_updated = 0

        for category in options['categories']:
            # Get the search term for this category
            search_term = category_to_search_term.get(category, category)
            self.stdout.write(f'\nScraping category: {category} (searching: {search_term})')

            # Queue for passing scraped data from scraper to saver
            data_queue = queue.Queue()

            def save_worker():
                nonlocal total_created, total_updated
                while True:
                    item = data_queue.get()
                    if item is None:  # Sentinel to stop
                        break
                    shop_name, shop_data = item
                    # Retry logic for saving products with connection cleanup
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            # Close old connections before each save attempt
                            close_old_connections()
                            
                            created, updated = self.save_shop_products(shop_name, shop_data, category)
                            total_created += created
                            total_updated += updated
                            
                            # Close connections after successful save
                            close_old_connections()
                            break
                        except Exception as e:
                            logger.error(f"Error saving products for {shop_name} ({category}), attempt {attempt+1}: {e}")
                            # Close connections on error
                            close_old_connections()
                            
                            if attempt < max_retries - 1:
                                import time; time.sleep(2 * (attempt + 1))
                            else:
                                self.stdout.write(self.style.ERROR(f"Failed to save products for {shop_name} ({category}) after {max_retries} attempts."))
                    data_queue.task_done()

            # Start save worker thread
            save_thread = threading.Thread(target=save_worker, daemon=True)
            save_thread.start()

            # Run scrapers with the search term (not category name)
            self.run_catalog_scrapers_streaming(search_term, data_queue, max_pages=25)

            # Wait for all saves to complete
            data_queue.join()
            data_queue.put(None)  # Stop signal
            save_thread.join()

        self.stdout.write(self.style.SUCCESS(f'\nCatalog populated: {total_created} products created, {total_updated} updated'))

    def create_categories(self, category_names):
        count = 0
        categories = ['Processor', 'Motherboard', 'RAM', 'SSD', 'HDD', 'Power Supply', 'Cabinet', 'GPU', 'CPU Cooler', 'Monitor', 'Keyboard', 'Mouse']
        
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
            {'name': 'StarTech', 'website_url': 'https://www.startech.com.bd', 'logo_url': 'https://www.startech.com.bd/image/catalog/logo.png', 'priority': 5},
            {'name': 'Ryans', 'website_url': 'https://www.ryans.com', 'logo_url': 'https://www.ryans.com/assets/images/ryans-logo.svg', 'priority': 4},
            {'name': 'SkyLand', 'website_url': 'https://www.skyland.com.bd', 'logo_url': 'https://www.skyland.com.bd/image/cache/wp/gp/skyland-logo-1398x471.webp', 'priority': 3},
            {'name': 'PcHouse', 'website_url': 'https://www.pchouse.com.bd', 'logo_url': 'https://www.pchouse.com.bd/image/catalog/unnamed.png', 'priority': 3},
            {'name': 'UltraTech', 'website_url': 'https://www.ultratech.com.bd', 'logo_url': 'https://www.ultratech.com.bd/image/cache/catalog/website/logo/ultra-technology-header-logo-500x500.png.webp', 'priority': 2},
            {'name': 'Binary', 'website_url': 'https://www.binarylogic.com.bd', 'logo_url': 'https://www.binarylogic.com.bd/images/brand_image/binary-logic.webp', 'priority': 2},
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

    def run_catalog_scrapers_streaming(self, category, data_queue, max_pages=50):
        """Run scrapers and stream results to queue as they complete"""
        def run_all_scrapers_streaming(cat, queue, max_pages):
            # All scrapers now accept max_pages argument
            scrapers = [
                ('StarTech', scrape_startech_catalog),
                ('SkyLand', scrape_skyland_catalog),
                ('PcHouse', scrape_pchouse_catalog),
                ('UltraTech', scrape_ultratech_catalog),
                ('PotakaIT', scrape_potakait_catalog),
                ('Ryans', scrape_ryans_catalog),
                ('Binary', scrape_binary_catalog),
            ]

            with ThreadPoolExecutor(max_workers=7) as executor:
                futures = {executor.submit(scraper, cat, max_pages): name for name, scraper in scrapers}

                for future in futures:
                    try:
                        result = future.result()
                        shop_name = futures[future]
                        queue.put((shop_name, result))
                    except Exception as e:
                        logger.error(f"Error scraping {futures[future]}: {e}")

        run_all_scrapers_streaming(category, data_queue, max_pages)

    def save_shop_products(self, shop_name, shop_data, category_name):
        """Save products from a single shop with proper connection management"""
        created_count = 0
        updated_count = 0
        
        self.stdout.write(f'  Saving {shop_name} products ({len(shop_data.get("products", []))} items)...')
        
        # Close old connections before starting
        close_old_connections()
        
        # Get the category
        category = Category.objects.filter(name__iexact=category_name).first()
        
        try:
            shop = Shop.objects.get(name=shop_name)
        except Shop.DoesNotExist:
            return 0, 0
        
        if shop_data.get('logo') and not shop.logo_url:
            shop.logo_url = shop_data['logo']
            shop.save()
        
        products_data = shop_data.get('products', [])
        if not products_data:
            return 0, 0
        
        # Process in small batches to prevent long-running transactions
        batch_size = 50
        for i in range(0, len(products_data), batch_size):
            batch = products_data[i:i + batch_size]
            
            # Close connections before each batch
            close_old_connections()
            
            try:
                with transaction.atomic():
                    created, updated = self._save_product_batch(batch, shop, category)
                    created_count += created
                    updated_count += updated
            except Exception as e:
                logger.error(f"Error saving batch for {shop_name}: {e}")
            finally:
                # Always close connections after batch
                close_old_connections()
        
        self.stdout.write(f'    {shop_name}: {created_count} created, {updated_count} updated')
        return created_count, updated_count
    
    def _save_product_batch(self, batch, shop, category):
        """Save a small batch of products - runs within a transaction"""
        created_count = 0
        updated_count = 0
        now = timezone.now()
        
        # Normalize URLs to prevent duplicates from pagination parameters
        # Extract URLs for this batch (after normalization)
        product_urls = []
        for p in batch:
            raw_url = p.get('link', '')
            if raw_url and raw_url not in ['#', 'Link not found', '']:
                normalized = normalize_product_url(raw_url)
                product_urls.append(normalized)
        
        # Fetch existing products for this batch only (not all shop products!)
        existing_by_url = {
            p.product_url: p for p in Product.objects.filter(
                shop=shop,
                product_url__in=product_urls
            ).only('id', 'name', 'product_url', 'current_price')
        }
        
        products_to_create = []
        products_to_update = []
        price_histories = []
        # Track URLs we're adding in this batch to prevent duplicates within the batch
        urls_in_batch = set(existing_by_url.keys())
        
        products_to_create = []
        products_to_update = []
        price_histories = []
        
        for product_data in batch:
            price = product_data.get('price')
            raw_url = product_data.get('link', '')
            product_name = product_data.get('name', 'Unknown Product')[:500]
            
            if not raw_url or raw_url in ['#', 'Link not found', '']:
                continue
            
            # Normalize the URL to prevent duplicates from pagination
            product_url = normalize_product_url(raw_url)
            
            # Skip if we already processed this URL in this batch
            if product_url in urls_in_batch and product_url not in existing_by_url:
                continue
            urls_in_batch.add(product_url)
            
            if isinstance(price, str) or price == 0 or price is None:
                stock_status = 'out_of_stock'
                is_available = False
                current_price = 0
            else:
                stock_status = 'in_stock'
                is_available = True
                current_price = price
            
            # Check if product exists by URL
            existing_product = existing_by_url.get(product_url)
            
            if existing_product:
                # Update existing
                existing_product.name = product_name
                existing_product.category = category
                existing_product.image_url = product_data.get('img', '')
                existing_product.current_price = current_price
                existing_product.stock_status = stock_status
                existing_product.is_available = is_available
                existing_product.last_scraped = now
                products_to_update.append(existing_product)
                updated_count += 1
                
                # Price history if changed
                if float(existing_product.current_price) != float(current_price):
                    price_histories.append(PriceHistory(
                        product=existing_product,
                        price=current_price,
                        stock_status=stock_status,
                        recorded_at=now
                    ))
            else:
                # Create new
                new_product = Product(
                    shop=shop,
                    product_url=product_url,
                    name=product_name,
                    category=category,
                    image_url=product_data.get('img', ''),
                    current_price=current_price,
                    stock_status=stock_status,
                    is_available=is_available,
                    last_scraped=now
                )
                products_to_create.append(new_product)
                created_count += 1
        
        # Bulk operations
        if products_to_create:
            created_products = Product.objects.bulk_create(products_to_create, batch_size=50, ignore_conflicts=True)
            for product in created_products:
                if product.pk:
                    price_histories.append(PriceHistory(
                        product=product,
                        price=product.current_price,
                        stock_status=product.stock_status,
                        recorded_at=now
                    ))
        
        if products_to_update:
            Product.objects.bulk_update(
                products_to_update,
                ['name', 'category', 'image_url', 'current_price', 'stock_status', 'is_available', 'last_scraped'],
                batch_size=50
            )
        
        if price_histories:
            PriceHistory.objects.bulk_create(price_histories, batch_size=50)
        
        return created_count, updated_count

