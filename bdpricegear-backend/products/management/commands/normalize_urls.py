from django.core.management.base import BaseCommand
from django.db import transaction
from products.models import Product
from products.utils.catalog_scraper import normalize_product_url


class Command(BaseCommand):
    help = 'Normalize all product URLs and remove duplicates'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Preview without making changes')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.WARNING('\n=== URL Normalization Tool ===\n'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE\n'))
        
        products = Product.objects.all().only('id', 'shop_id', 'product_url', 'updated_at')
        total = products.count()
        self.stdout.write(f'Scanning {total} products...')
        
        # Track: (shop_id, normalized_url) -> best product to keep
        url_map = {}
        duplicates_to_delete = []
        urls_to_normalize = []
        
        for i, p in enumerate(products.iterator(chunk_size=1000)):
            normalized = normalize_product_url(p.product_url)
            key = (p.shop_id, normalized)
            
            if key in url_map:
                # Duplicate found - keep the newest one
                existing_id, existing_updated = url_map[key]
                if p.updated_at > existing_updated:
                    duplicates_to_delete.append(existing_id)
                    url_map[key] = (p.id, p.updated_at)
                    if normalized != p.product_url:
                        urls_to_normalize.append((p.id, normalized))
                else:
                    duplicates_to_delete.append(p.id)
            else:
                url_map[key] = (p.id, p.updated_at)
                if normalized != p.product_url:
                    urls_to_normalize.append((p.id, normalized))
            
            if (i + 1) % 5000 == 0:
                self.stdout.write(f'  Scanned {i+1}/{total}')
        
        self.stdout.write(f'\nFound {len(duplicates_to_delete)} duplicates to delete')
        self.stdout.write(f'Found {len(urls_to_normalize)} URLs to normalize')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nRun without --dry-run to apply changes'))
            return
        
        # Delete duplicates in batches
        if duplicates_to_delete:
            self.stdout.write(f'\nDeleting {len(duplicates_to_delete)} duplicates...')
            batch_size = 500
            deleted_total = 0
            for i in range(0, len(duplicates_to_delete), batch_size):
                batch = duplicates_to_delete[i:i + batch_size]
                deleted, _ = Product.objects.filter(id__in=batch).delete()
                deleted_total += deleted
            self.stdout.write(f'  Deleted {deleted_total} products')
        
        # Update URLs in batches
        if urls_to_normalize:
            self.stdout.write(f'\nNormalizing {len(urls_to_normalize)} URLs...')
            batch_size = 500
            updated_total = 0
            for i in range(0, len(urls_to_normalize), batch_size):
                batch = urls_to_normalize[i:i + batch_size]
                ids = [item[0] for item in batch]
                products_to_update = list(Product.objects.filter(id__in=ids))
                
                # Create lookup for normalized URLs
                url_lookup = {item[0]: item[1] for item in batch}
                
                for p in products_to_update:
                    p.product_url = url_lookup[p.id]
                
                Product.objects.bulk_update(products_to_update, ['product_url'])
                updated_total += len(products_to_update)
            
            self.stdout.write(f'  Updated {updated_total} URLs')
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Done! Total products: {Product.objects.count()}'))
