from django.core.management.base import BaseCommand
from django.db import transaction, connection
from products.models import Product, Category

# Import the filter function from populate_catalog
from products.management.commands.populate_catalog import is_product_in_category


class Command(BaseCommand):
    help = 'Remove miscategorized products (products that dont belong to their assigned category)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be removed without actually removing'
        )
        parser.add_argument(
            '--category',
            type=str,
            help='Only check products in a specific category'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        category_filter = options['category']
        
        self.stdout.write(self.style.WARNING('\n=== Miscategorized Product Remover ===\n'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))
        
        # Build filter
        where_clause = ""
        if category_filter:
            self.stdout.write(f'Filtering by category: {category_filter}\n')
            where_clause = f"WHERE c.name ILIKE '{category_filter}'"
        
        # Get all products with their current category in one query
        self.stdout.write('Loading products...')
        query = f"""
            SELECT p.id, p.name, c.name as category_name
            FROM products_product p
            LEFT JOIN products_category c ON p.category_id = c.id
            {where_clause}
        """
        
        with connection.cursor() as cursor:
            cursor.execute(query)
            products = cursor.fetchall()
        
        total_products = len(products)
        self.stdout.write(f'Checking {total_products:,} products...\n')
        
        # Track products to remove
        ids_to_remove = []
        removal_reasons = {}  # {category: count}
        
        for i, (product_id, product_name, category_name) in enumerate(products):
            if i > 0 and i % 5000 == 0:
                self.stdout.write(f'  Analyzed {i:,} / {total_products:,}')
            
            if category_name and not is_product_in_category(product_name, category_name):
                ids_to_remove.append(product_id)
                removal_reasons[category_name] = removal_reasons.get(category_name, 0) + 1
        
        self.stdout.write(f'  Analyzed {total_products:,} / {total_products:,}')
        
        # Report
        self.stdout.write('\n' + self.style.WARNING('=== Miscategorized Products by Category ==='))
        
        if removal_reasons:
            for cat, count in sorted(removal_reasons.items(), key=lambda x: -x[1]):
                self.stdout.write(f'  {cat}: {count:,} products dont belong')
        
        total_to_remove = len(ids_to_remove)
        
        if total_to_remove == 0:
            self.stdout.write(self.style.SUCCESS('\n✓ All products are correctly categorized!'))
        elif dry_run:
            self.stdout.write(self.style.WARNING(f'\n{total_to_remove:,} miscategorized products would be removed'))
            self.stdout.write('Run without --dry-run to remove them')
        else:
            # Remove in batches
            self.stdout.write(f'\nRemoving {total_to_remove:,} miscategorized products...')
            batch_size = 1000
            removed = 0
            
            for i in range(0, len(ids_to_remove), batch_size):
                batch = ids_to_remove[i:i + batch_size]
                with transaction.atomic():
                    deleted, _ = Product.objects.filter(id__in=batch).delete()
                    removed += deleted
            
            self.stdout.write(self.style.SUCCESS(f'\n✓ Removed {removed:,} miscategorized products'))
            self.stdout.write(f'  Remaining products: {Product.objects.count():,}')
