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

            def save_worker():
                nonlocal total_created, total_updated
                while True:
                    item = data_queue.get()
                    if item is None:  # Sentinel to stop
                        break
                    shop_name, shop_data = item
                    # Retry logic for saving products
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            created, updated = self.save_shop_products(shop_name, shop_data, category)
                            total_created += created
                            total_updated += updated
                            break
                        except Exception as e:
                            logger.error(f"Error saving products for {shop_name} ({category}), attempt {attempt+1}: {e}")
                            if attempt < max_retries - 1:
                                import time; time.sleep(2 * (attempt + 1))
                            else:
                                self.stdout.write(self.style.ERROR(f"Failed to save products for {shop_name} ({category}) after {max_retries} attempts."))
                    data_queue.task_done()

            # Start save worker thread
            save_thread = threading.Thread(target=save_worker, daemon=True)
            save_thread.start()

            # Run scrapers and feed queue
            self.run_catalog_scrapers_streaming(category, data_queue, max_pages=50)

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
        """Save products from a single shop with optimized bulk operations"""
        created_count = 0
        updated_count = 0
        
        self.stdout.write(f'  Saving {shop_name} products ({len(shop_data.get("products", []))} items)...')
        
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
        
        # Extract all product URLs and names for this batch
        product_urls = [p.get('link', '') for p in products_data if p.get('link') and p.get('link') not in ['#', 'Link not found', '']]
        product_names = [p.get('name', '')[:500] for p in products_data if p.get('name')]
        
        # Fetch existing products by URL in one query
        existing_products_by_url = {
            p.product_url: p for p in Product.objects.filter(
                shop=shop,
                product_url__in=product_urls
            ).select_related('category', 'shop')
        }
        
        # Fetch existing products by NAME in one query (DUPLICATE PREVENTION)
        existing_products_by_name = {
            p.name: p for p in Product.objects.filter(
                shop=shop,
                name__in=product_names
            ).select_related('category', 'shop')
        }
        
        # Fetch latest price history for existing products in one query
        all_existing_products = list(existing_products_by_url.values()) + list(existing_products_by_name.values())
        existing_product_ids = list(set(all_existing_products))  # Remove duplicates
        latest_prices = {}
        if existing_product_ids:
            from django.db.models import Max
            price_history_qs = PriceHistory.objects.filter(
                product__in=existing_product_ids
            ).values('product_id').annotate(latest_price=Max('price'))
            latest_prices = {ph['product_id']: ph['latest_price'] for ph in price_history_qs}
        
        products_to_create = []
        products_to_update = []
        price_histories_to_create = []
        now = timezone.now()
        
        for product_data in products_data:
            price = product_data.get('price')
            product_url = product_data.get('link', '')
            product_name = product_data.get('name', 'Unknown Product')[:500]
            
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
            
            # DUPLICATE PREVENTION: Check by name first, then by URL
            product = existing_products_by_name.get(product_name) or existing_products_by_url.get(product_url)
            
            if product:
                # Update existing product (found by name or URL)
                product.name = product_name
                product.product_url = product_url  # Update URL if different
                product.category = category
                product.image_url = product_data.get('img', '')
                product.current_price = current_price
                product.stock_status = stock_status
                product.is_available = is_available
                product.last_scraped = now
                products_to_update.append(product)
                updated_count += 1
                
                # Check if price changed
                latest_price = latest_prices.get(product.id)
                if latest_price is None or float(latest_price) != float(current_price):
                    price_histories_to_create.append(
                        PriceHistory(
                            product=product,
                            price=current_price,
                            stock_status=stock_status,
                            recorded_at=now
                        )
                    )
            else:
                # Create new product
                new_product = Product(
                    shop=shop,
                    product_url=product_url,
                    name=product_data.get('name', 'Unknown Product')[:500],
                    category=category,
                    image_url=product_data.get('img', ''),
                    current_price=current_price,
                    stock_status=stock_status,
                    is_available=is_available,
                    last_scraped=now
                )
                products_to_create.append(new_product)
                created_count += 1
        
        # Bulk create new products
        if products_to_create:
            self.stdout.write(f'    Creating {len(products_to_create)} new products...')
            created_products = Product.objects.bulk_create(
                products_to_create, 
                batch_size=500,
                ignore_conflicts=True
            )
            # Add price history for new products
            for product in created_products:
                if product.pk:  # Only add history if product was actually created
                    price_histories_to_create.append(
                        PriceHistory(
                            product=product,
                            price=product.current_price,
                            stock_status=product.stock_status,
                            recorded_at=now
                        )
                    )
        
        # Bulk update existing products
        if products_to_update:
            self.stdout.write(f'    Updating {len(products_to_update)} existing products...')
            Product.objects.bulk_update(
                products_to_update,
                ['name', 'category', 'image_url', 'current_price', 'stock_status', 'is_available', 'last_scraped'],
                batch_size=500
            )
        
        # Bulk create price histories
        if price_histories_to_create:
            self.stdout.write(f'    Creating {len(price_histories_to_create)} price history records...')
            PriceHistory.objects.bulk_create(price_histories_to_create, batch_size=500)
        
        self.stdout.write(f'    {shop_name}: {created_count} created, {updated_count} updated')
        return created_count, updated_count

