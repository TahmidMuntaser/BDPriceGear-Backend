
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from products.models import Product, PriceHistory


class Command(BaseCommand):
    help = 'Delete all products and related data older than 6 months (full database cleanup)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--months',
            type=int,
            default=6,
            help='Delete products not updated in this many months (default: 6)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        months = options['months']
        dry_run = options['dry_run']
        
        cutoff_date = timezone.now() - timedelta(days=months * 30)
        
        self.stdout.write(self.style.WARNING(f'\nFull Database Cleanup'))
        self.stdout.write(f'   Cutoff date: {cutoff_date.strftime("%Y-%m-%d %H:%M:%S")}')
        self.stdout.write(f'   Will delete products not updated in {months} months\n')
        
        old_products = Product.objects.filter(updated_at__lt=cutoff_date)
        products_count = old_products.count()
        
        if products_count == 0:
            self.stdout.write(self.style.SUCCESS('No old products found. Database is clean!'))
            return
        
        price_history_count = PriceHistory.objects.filter(product__in=old_products).count()
        
        total_products = Product.objects.count()
        total_history = PriceHistory.objects.count()
        
        self.stdout.write(f'Statistics:')
        self.stdout.write(f'   Total products: {total_products:,}')
        self.stdout.write(f'   Products to delete: {products_count:,} ({products_count/total_products*100:.1f}%)')
        self.stdout.write(f'   Associated price history to delete: {price_history_count:,}')
        self.stdout.write(f'   Products to keep: {total_products - products_count:,}\n')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be deleted'))
            self.stdout.write(f'   Run without --dry-run to actually delete {products_count:,} products\n')
            
            sample = old_products.select_related('shop', 'category')[:10]
            if sample:
                self.stdout.write('Sample products that would be deleted:')
                for product in sample:
                    self.stdout.write(f'   {product.name[:60]} - {product.shop.name} (Last update: {product.updated_at.strftime("%Y-%m-%d")})')
        else:
            self.stdout.write(self.style.WARNING(f'About to delete {products_count:,} products and {price_history_count:,} price history records!'))
            confirm = input('   Type "yes" to confirm deletion: ')
            
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('\nCleanup cancelled'))
                return
            
            self.stdout.write('\nDeleting old products and associated data...')
            deleted_count, details = old_products.delete()
            
            self.stdout.write(self.style.SUCCESS(f'\nSuccessfully deleted {deleted_count:,} records'))
            self.stdout.write(f'   Products deleted: {products_count:,}')
            self.stdout.write(f'   Price history deleted: {price_history_count:,}')
            self.stdout.write(f'   Remaining products: {Product.objects.count():,}')
            self.stdout.write(f'   Remaining price history: {PriceHistory.objects.count():,}')
            self.stdout.write(self.style.SUCCESS('   Database cleanup completed!\n'))
