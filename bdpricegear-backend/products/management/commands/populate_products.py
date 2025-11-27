
# Django management command to populate database with products.

# Usage:
#     python manage.py populate_products
#     python manage.py populate_products --search laptop mouse
#     python manage.py populate_products --limit 5


from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
import asyncio
from playwright.async_api import async_playwright
from concurrent.futures import ThreadPoolExecutor

from products.models import Product, Shop, Category, PriceHistory
from products.utils.scraper import (
    scrape_startech, scrape_ryans, scrape_skyland,
    scrape_pchouse, scrape_ultratech, scrape_binary_playwright, scrape_potakait
)


class Command(BaseCommand):
    help = 'Populate database with categories, shops, and products'

    def add_arguments(self, parser):
        parser.add_argument(
            '--search',
            nargs='+',
            type=str,
            default=['laptop', 'mouse', 'keyboard', 'monitor', 'webcam', 'Microphone', 'speaker', 'headphone', 'ram', 'ssd', 'hdd'],
            help='Search terms to scrape (default: laptop, mouse, keyboard, monitor)'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of products per shop (for testing)'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting database population...'))
        
        # Step 1: Create categories
        self.stdout.write('\n📁 Creating categories...')
        categories_created = self.create_categories(options['search'])
        self.stdout.write(self.style.SUCCESS(f'✅ Created {categories_created} categories'))
        
        # Step 2: Create shops
        self.stdout.write('\n🏪 Creating shops...')
        shops_created = self.create_shops()
        self.stdout.write(self.style.SUCCESS(f'✅ Created {shops_created} shops'))
        
        # Step 3: Scrape and save products
        self.stdout.write('\n🔍 Scraping products...')
        total_created = 0
        total_updated = 0
        
        for search_term in options['search']:
            self.stdout.write(f'\n  Searching for: {search_term}')
            
            # Run scrapers
            scraped_data = self.run_scrapers(search_term)
            
            # Save to database
            created, updated = self.save_products(scraped_data, search_term, options['limit'])
            total_created += created
            total_updated += updated
            
            self.stdout.write(f'    ✓ {created} created, {updated} updated')
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'\n✨ Done! Total: {total_created} products created, {total_updated} updated'))
        self.stdout.write(self.style.SUCCESS(f'\n🎉 Database populated successfully!'))

    def create_categories(self, search_terms):
        """Create categories from search terms"""
        count = 0
        categories = [
            'Laptop',
            'Mouse',
            'Keyboard',
            'Monitor',
            'Headphone',
            'Speaker',
            'Webcam',
            'Microphone',
            'RAM',
            'SSD',
            'HDD',
        ]
        
        for cat_name in categories:
            _, created = Category.objects.update_or_create(
                name=cat_name,
                defaults={'is_active': True}
            )
            if created:
                count += 1
        
        return count

    def create_shops(self):
        """Create shop records"""
        count = 0
        shops = [
            {
                'name': 'StarTech',
                'website_url': 'https://www.startech.com.bd',
                'logo_url': 'https://www.startech.com.bd/catalog/view/theme/starship/images/logo.png',
                'priority': 5
            },
            {
                'name': 'Ryans',
                'website_url': 'https://www.ryans.com',
                'logo_url': 'https://www.ryans.com/wp-content/themes/ryans/img/logo.png',
                'priority': 4
            },
            {
                'name': 'SkyLand',
                'website_url': 'https://www.skyland.com.bd',
                'logo_url': 'https://www.skyland.com.bd/image/catalog/logo.png',
                'priority': 3
            },
            {
                'name': 'PcHouse',
                'website_url': 'https://www.pchouse.com.bd',
                'logo_url': 'https://www.pchouse.com.bd/image/catalog/unnamed.png',
                'priority': 3
            },
            {
                'name': 'UltraTech',
                'website_url': 'https://www.ultratech.com.bd',
                'logo_url': 'https://www.ultratech.com.bd/image/catalog/logo.png',
                'priority': 2
            },
            {
                'name': 'Binary',
                'website_url': 'https://www.binarylogic.com.bd',
                'logo_url': 'https://www.binarylogic.com.bd/images/logo.png',
                'priority': 2
            },
            {
                'name': 'PotakaIT',
                'website_url': 'https://www.potakait.com',
                'logo_url': 'https://www.potakait.com/image/catalog/logo.png',
                'priority': 1
            },
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

    def run_scrapers(self, search_term):
        """Run all scrapers for a search term"""
        
        async def gather_all_scrapers(product):
            # Dynamic scrapers
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

            # Static scrapers
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
    def save_products(self, scraped_data, search_term, limit=None):
        """Save scraped products to database"""
        created_count = 0
        updated_count = 0
        
        # Try to find matching category
        category = Category.objects.filter(name__iexact=search_term).first()
        
        for shop_name, shop_data in scraped_data.items():
            # Get shop
            try:
                shop = Shop.objects.get(name=shop_name)
            except Shop.DoesNotExist:
                continue
            
            # Update shop logo if available
            if shop_data.get('logo') and not shop.logo_url:
                shop.logo_url = shop_data['logo']
                shop.save()
            
            # Process products
            products = shop_data.get('products', [])
            if limit:
                products = products[:limit]
            
            for product_data in products:
                # Get price and validate
                price = product_data.get('price')
                
                product_url = product_data.get('link', '')
                if not product_url or product_url == '#' or product_url == 'Link not found':
                    continue
                
                # Determine stock status and availability based on price
                if isinstance(price, str) or price == 0 or price is None:
                    # Invalid price means out of stock
                    stock_status = 'out_of_stock'
                    is_available = False
                    current_price = 0
                else:
                    # Valid price means in stock
                    stock_status = 'in_stock' if product_data.get('in_stock', True) else 'out_of_stock'
                    is_available = stock_status == 'in_stock'
                    current_price = price
                
                # Create/update product
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
                
                # Record price history
                latest_history = product.price_history.first()
                if not latest_history or latest_history.price != product.current_price:
                    PriceHistory.objects.create(
                        product=product,
                        price=product.current_price,
                        stock_status=product.stock_status,
                        recorded_at=timezone.now()
                    )
        
        return created_count, updated_count
