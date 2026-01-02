from django.core.management.base import BaseCommand
from products.models import Product, PriceHistory
from django.db.models import Count


class Command(BaseCommand):
    help = 'Remove duplicate products based on normalized name + shop'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n=== DRY RUN MODE ===\n'))
        else:
            self.stdout.write(self.style.WARNING('\n=== REMOVING DUPLICATES ===\n'))
        
        def normalize_name(name):
            """Normalize product name by removing extra spaces and converting to lowercase"""
            return ' '.join(name.strip().lower().split())
        
        def normalize_url(url):
            """Normalize URL for comparison"""
            return url.strip().lower()
        
        # Get all products
        all_products = Product.objects.all().select_related('shop', 'category')
        
        # Group by shop, normalized name, AND normalized URL
        products_by_shop_name_url = {}
        for product in all_products:
            key = (product.shop.id, normalize_name(product.name), normalize_url(product.product_url))
            if key not in products_by_shop_name_url:
                products_by_shop_name_url[key] = []
            products_by_shop_name_url[key].append(product)
        
        # Find duplicates (same shop + same name + same URL)
        duplicates_found = 0
        duplicates_deleted = 0
        
        for (shop_id, normalized_name, normalized_url), products in products_by_shop_name_url.items():
            if len(products) > 1:
                duplicates_found += len(products) - 1
                
                # Sort by last_scraped (keep most recent) or by id (keep oldest)
                products.sort(key=lambda p: p.last_scraped if p.last_scraped else p.created_at, reverse=True)
                
                # Keep the first one, delete the rest
                keep_product = products[0]
                delete_products = products[1:]
                
                self.stdout.write(f'\nDuplicate group: {keep_product.name} ({keep_product.shop.name})')
                self.stdout.write(f'  KEEPING: ID={keep_product.id}, URL={keep_product.product_url}')
                
                for dup in delete_products:
                    self.stdout.write(f'  DELETING: ID={dup.id}, URL={dup.product_url}')
                    if not dry_run:
                        dup.delete()
                        duplicates_deleted += 1
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'\n✓ Found {duplicates_found} duplicate products'))
            self.stdout.write(self.style.WARNING('Run without --dry-run to delete them'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n✓ Deleted {duplicates_deleted} duplicate products'))
            remaining = Product.objects.count()
            self.stdout.write(f'Remaining products: {remaining}')
