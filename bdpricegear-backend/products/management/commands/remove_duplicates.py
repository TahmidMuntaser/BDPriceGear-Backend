from django.core.management.base import BaseCommand
from django.db.models import Count
from products.models import Product, PriceHistory
from django.db import transaction
import urllib.parse


def normalize_product_url(url):
    """
    Normalize product URL by removing pagination and search query parameters.
    This helps identify duplicate products that have different page numbers.
    """
    if not url:
        return url
    
    try:
        parsed = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed.query)
        
        # Remove pagination and search-related query parameters
        params_to_remove = ['page', 'search', 'q', 'keyword', 'sort', 'order', 'limit']
        filtered_params = {
            k: v for k, v in query_params.items() 
            if k.lower() not in params_to_remove
        }
        
        # Rebuild the URL without the removed parameters
        new_query = urllib.parse.urlencode(filtered_params, doseq=True) if filtered_params else ''
        normalized = urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            ''
        ))
        
        return normalized
    except Exception:
        return url


class Command(BaseCommand):
    help = 'Remove duplicate products (same name + shop) keeping only the most recent one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--shop',
            type=str,
            help='Only remove duplicates for a specific shop name'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of duplicate groups to process'
        )
        parser.add_argument(
            '--normalize-urls',
            action='store_true',
            help='Also find duplicates by normalizing URLs (removing page/search params)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        shop_filter = options['shop']
        limit = options['limit']
        normalize_urls = options['normalize_urls']
        
        self.stdout.write(self.style.WARNING('\n=== Product Duplicate Removal Tool ===\n'))
        
        if normalize_urls:
            self.stdout.write(self.style.WARNING('URL normalization enabled - will also detect duplicates with different page params\n'))
            self.remove_url_normalized_duplicates(dry_run, shop_filter, limit)
        else:
            self.remove_name_shop_duplicates(dry_run, shop_filter, limit)
    
    def remove_url_normalized_duplicates(self, dry_run, shop_filter, limit):
        """Remove duplicates based on normalized URL (removing pagination params) - OPTIMIZED"""
        from products.models import Shop
        
        self.stdout.write('Scanning for duplicates (this may take a moment)...')
        
        # Build base query
        products_query = Product.objects.all()
        
        if shop_filter:
            try:
                shop = Shop.objects.get(name__iexact=shop_filter)
                products_query = products_query.filter(shop=shop)
                self.stdout.write(f'Filtering by shop: {shop.name}\n')
            except Shop.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Shop "{shop_filter}" not found'))
                return
        
        # Only fetch the fields we need - much faster!
        products_query = products_query.only('id', 'name', 'shop_id', 'product_url', 'updated_at')
        
        # Process in batches using iterator to reduce memory
        products_by_normalized = {}
        batch_size = 5000
        total_processed = 0
        
        for product in products_query.iterator(chunk_size=batch_size):
            normalized_url = normalize_product_url(product.product_url)
            key = (product.shop_id, normalized_url)
            if key not in products_by_normalized:
                products_by_normalized[key] = []
            # Store only what we need: (id, name, updated_at, original_url)
            products_by_normalized[key].append({
                'id': product.id,
                'name': product.name,
                'updated_at': product.updated_at,
                'url': product.product_url,
                'shop_id': product.shop_id
            })
            total_processed += 1
            if total_processed % 10000 == 0:
                self.stdout.write(f'  Processed {total_processed:,} products...')
        
        self.stdout.write(f'  Total processed: {total_processed:,} products')
        
        # Find groups with duplicates
        duplicate_groups = {k: v for k, v in products_by_normalized.items() if len(v) > 1}
        
        # Free memory
        del products_by_normalized
        
        if limit:
            duplicate_groups = dict(list(duplicate_groups.items())[:limit])
        
        if not duplicate_groups:
            self.stdout.write(self.style.SUCCESS('✓ No URL-based duplicate products found. Database is clean!'))
            return
        
        total_duplicates = sum(len(v) - 1 for v in duplicate_groups.values())
        
        self.stdout.write(f'\nFound {len(duplicate_groups)} duplicate groups (by normalized URL)')
        self.stdout.write(f'Total duplicate products to remove: {total_duplicates}\n')
        
        # Show sample duplicates
        self.stdout.write(self.style.WARNING('Sample duplicate products:'))
        shop_names = {s.id: s.name for s in Shop.objects.all()}
        for i, ((shop_id, norm_url), products) in enumerate(list(duplicate_groups.items())[:10], 1):
            self.stdout.write(
                f"  {i}. '{products[0]['name'][:50]}...' from {shop_names.get(shop_id, 'Unknown')} "
                f"({len(products)} copies)"
            )
            for p in products:
                self.stdout.write(f"      - ID: {p['id']}, URL: {p['url'][:70]}...")
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN MODE - No data will be deleted'))
            self.stdout.write(f'Run without --dry-run to remove {total_duplicates} duplicates\n')
            return
        
        # Confirm deletion
        self.stdout.write(self.style.WARNING(
            f'\n⚠ About to delete {total_duplicates} duplicate products!'
        ))
        confirm = input('Type "yes" to confirm deletion: ')
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.ERROR('Deletion cancelled'))
            return
        
        # Delete duplicates in batches for better performance
        deleted_count = 0
        ids_to_delete = []
        
        for (shop_id, norm_url), products in duplicate_groups.items():
            # Sort by updated_at desc, keep the most recent
            products.sort(key=lambda p: p['updated_at'], reverse=True)
            
            # Collect IDs to delete (skip the first/newest)
            for dup in products[1:]:
                ids_to_delete.append(dup['id'])
        
        # Delete in batches
        batch_size = 1000
        self.stdout.write(f'Deleting {len(ids_to_delete)} duplicates in batches...')
        
        for i in range(0, len(ids_to_delete), batch_size):
            batch = ids_to_delete[i:i + batch_size]
            with transaction.atomic():
                deleted, _ = Product.objects.filter(id__in=batch).delete()
                deleted_count += deleted
            self.stdout.write(f'  Deleted {min(i + batch_size, len(ids_to_delete)):,} / {len(ids_to_delete):,}')
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully removed {deleted_count} duplicate products'))
        self.stdout.write(f'  Remaining products: {Product.objects.count():,}')

    def remove_name_shop_duplicates(self, dry_run, shop_filter, limit):
        """Original method: Remove duplicates based on name + shop"""
        # Find duplicates (same name + shop)
        duplicates_query = Product.objects.values('name', 'shop').annotate(
            count=Count('id')
        ).filter(count__gt=1).order_by('-count')
        
        if shop_filter:
            from products.models import Shop
            try:
                shop = Shop.objects.get(name__iexact=shop_filter)
                duplicates_query = duplicates_query.filter(shop=shop.id)
                self.stdout.write(f'Filtering by shop: {shop.name}\n')
            except Shop.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Shop "{shop_filter}" not found'))
                return
        
        if limit:
            duplicates_query = duplicates_query[:limit]
        
        duplicates = list(duplicates_query)
        
        if not duplicates:
            self.stdout.write(self.style.SUCCESS('✓ No duplicate products found. Database is clean!'))
            return
        
        total_duplicate_groups = len(duplicates)
        total_products_to_delete = sum(d['count'] - 1 for d in duplicates)
        
        self.stdout.write(f'Found duplicate product groups: {total_duplicate_groups}')
        self.stdout.write(f'Total duplicate products to remove: {total_products_to_delete}\n')
        
        # Show sample duplicates
        self.stdout.write(self.style.WARNING('Top duplicate products:'))
        for i, dup in enumerate(duplicates[:10], 1):
            shop_name = Product.objects.filter(
                name=dup['name'], 
                shop_id=dup['shop']
            ).first().shop.name
            self.stdout.write(
                f"  {i}. '{dup['name'][:60]}...' from {shop_name} "
                f"({dup['count']} copies)"
            )
        
        if total_duplicate_groups > 10:
            self.stdout.write(f"  ... and {total_duplicate_groups - 10} more duplicate groups\n")
        else:
            self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be deleted'))
            self.stdout.write(f'Run without --dry-run to remove {total_products_to_delete} duplicates\n')
            
            # Show detailed example of one duplicate group
            if duplicates:
                example = duplicates[0]
                example_products = Product.objects.filter(
                    name=example['name'],
                    shop_id=example['shop']
                ).order_by('-updated_at')
                
                self.stdout.write('\nExample duplicate group:')
                self.stdout.write(f"  Product: {example['name'][:80]}")
                for idx, p in enumerate(example_products):
                    status = '✓ KEEP (most recent)' if idx == 0 else '✗ DELETE'
                    self.stdout.write(
                        f"    [{status}] ID: {p.id} | "
                        f"Price: ৳{p.current_price} | "
                        f"Updated: {p.updated_at.strftime('%Y-%m-%d %H:%M')} | "
                        f"URL: {p.product_url[:50]}..."
                    )
            return
        
        # Confirm deletion
        self.stdout.write(self.style.WARNING(
            f'\n⚠ About to delete {total_products_to_delete} duplicate products!'
        ))
        self.stdout.write('Strategy: Keep the most recently updated product, delete older copies\n')
        
        confirm = input('Type "yes" to confirm deletion: ')
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.ERROR('Deletion cancelled'))
            return
        
        # Use raw SQL to efficiently get IDs to delete in ONE query
        self.stdout.write('Collecting product IDs to delete (using optimized query)...')
        
        from django.db import connection
        
        # This query finds all product IDs that are NOT the most recent for each name+shop group
        query = """
            WITH ranked AS (
                SELECT id, name, shop_id,
                       ROW_NUMBER() OVER (PARTITION BY name, shop_id ORDER BY updated_at DESC) as rn
                FROM products_product
            )
            SELECT id FROM ranked WHERE rn > 1
        """
        
        with connection.cursor() as cursor:
            cursor.execute(query)
            ids_to_delete = [row[0] for row in cursor.fetchall()]
        
        if not ids_to_delete:
            self.stdout.write(self.style.SUCCESS('No duplicates to delete!'))
            return
        
        self.stdout.write(f'Found {len(ids_to_delete)} products to delete')
        
        # Delete in small batches to avoid deadlocks
        deleted_count = 0
        batch_size = 500
        total_batches = (len(ids_to_delete) + batch_size - 1) // batch_size
        
        self.stdout.write(f'Deleting in {total_batches} batches...')
        
        import time
        for i in range(0, len(ids_to_delete), batch_size):
            batch = ids_to_delete[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            # Retry logic for deadlocks
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        deleted, _ = Product.objects.filter(id__in=batch).delete()
                        deleted_count += deleted
                    break  # Success
                except Exception as e:
                    if 'deadlock' in str(e).lower() and attempt < max_retries - 1:
                        self.stdout.write(f'  Deadlock on batch {batch_num}, retrying...')
                        time.sleep(1)
                    else:
                        raise
            
            self.stdout.write(f'  Batch {batch_num}/{total_batches}: Deleted {deleted} products')
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully removed {deleted_count} duplicate products'))
        self.stdout.write(f'  Remaining products: {Product.objects.count():,}')
        self.stdout.write(self.style.SUCCESS('  Database cleanup completed!\n'))
