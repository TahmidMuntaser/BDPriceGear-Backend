from django.core.management.base import BaseCommand
from products.models import Product, PriceHistory


class Command(BaseCommand):
    help = 'Delete ALL products and price history data (keeps tables, categories, and shops)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt'
        )

    def handle(self, *args, **options):
        # Count current data
        product_count = Product.objects.count()
        price_history_count = PriceHistory.objects.count()
        
        self.stdout.write(self.style.WARNING('\n=== DELETE ALL PRODUCT DATA ===\n'))
        self.stdout.write(f'Products to delete: {product_count:,}')
        self.stdout.write(f'Price history records to delete: {price_history_count:,}')
        self.stdout.write('\n⚠️  This will DELETE ALL product data!')
        self.stdout.write('✓ Tables will remain (structure intact)')
        self.stdout.write('✓ Categories will remain')
        self.stdout.write('✓ Shops will remain\n')
        
        if not options['confirm']:
            confirm = input('Type "DELETE ALL" to confirm: ')
            if confirm != 'DELETE ALL':
                self.stdout.write(self.style.ERROR('Cancelled - no data deleted'))
                return
        
        self.stdout.write('\nDeleting all products and price history...')
        
        # Delete all products (price history will cascade delete automatically)
        deleted_products, details = Product.objects.all().delete()
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully deleted all data!'))
        self.stdout.write(f'  Products deleted: {product_count:,}')
        self.stdout.write(f'  Price history deleted: {price_history_count:,}')
        self.stdout.write(f'  Total records deleted: {deleted_products:,}')
        
        # Verify
        remaining_products = Product.objects.count()
        remaining_history = PriceHistory.objects.count()
        
        self.stdout.write(f'\n  Remaining products: {remaining_products}')
        self.stdout.write(f'  Remaining price history: {remaining_history}')
        self.stdout.write(self.style.SUCCESS('\n✓ Database cleaned successfully!\n'))
