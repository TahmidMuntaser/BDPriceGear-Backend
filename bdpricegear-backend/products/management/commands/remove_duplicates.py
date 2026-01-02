from django.core.management.base import BaseCommand
from django.db.models import Count
from products.models import Product, PriceHistory
from django.db import transaction


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

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        shop_filter = options['shop']
        limit = options['limit']
        
        self.stdout.write(self.style.WARNING('\n=== Product Duplicate Removal Tool ===\n'))
        
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
        
        # Delete duplicates
        deleted_count = 0
        price_history_deleted = 0
        
        with transaction.atomic():
            for dup in duplicates:
                # Get all products with same name and shop, ordered by most recent first
                products = Product.objects.filter(
                    name=dup['name'],
                    shop_id=dup['shop']
                ).order_by('-updated_at')
                
                # Keep the first one (most recent), delete the rest
                products_to_delete = products[1:]
                
                for product in products_to_delete:
                    # Count price history before deleting
                    ph_count = product.price_history.count()
                    price_history_deleted += ph_count
                    
                    product.delete()
                    deleted_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully removed {deleted_count} duplicate products'))
        self.stdout.write(f'  Associated price history deleted: {price_history_deleted}')
        self.stdout.write(f'  Remaining products: {Product.objects.count():,}')
        self.stdout.write(self.style.SUCCESS('  Database cleanup completed!\n'))
