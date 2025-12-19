"""
Django management command to cleanup old price history data.

This command removes price history records older than 3 months to save database storage.
Run this periodically (weekly/monthly) via cron job or scheduled task.

Usage:
    python manage.py cleanup_price_history
    python manage.py cleanup_price_history --days 90
    python manage.py cleanup_price_history --dry-run
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from products.models import PriceHistory


class Command(BaseCommand):
    help = 'Delete price history records older than specified days (default: 90 days / 3 months)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Delete records older than this many days (default: 90)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write(self.style.WARNING(f'\nPrice History Cleanup'))
        self.stdout.write(f'   Cutoff date: {cutoff_date.strftime("%Y-%m-%d %H:%M:%S")}')
        self.stdout.write(f'   Will delete records older than {days} days\n')
        
        old_records = PriceHistory.objects.filter(recorded_at__lt=cutoff_date)
        count = old_records.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No old records found. Database is clean!'))
            return
        
        total_records = PriceHistory.objects.count()
        percentage = (count / total_records * 100) if total_records > 0 else 0
        
        self.stdout.write(f'Statistics:')
        self.stdout.write(f'   Total price history records: {total_records:,}')
        self.stdout.write(f'   Records to delete: {count:,} ({percentage:.1f}%)')
        self.stdout.write(f'   Records to keep: {total_records - count:,}\n')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No records will be deleted'))
            self.stdout.write(f'   Run without --dry-run to actually delete {count:,} records\n')
            
            sample = old_records.select_related('product')[:5]
            if sample:
                self.stdout.write('Sample records that would be deleted:')
                for record in sample:
                    self.stdout.write(f'   {record.product.name[:50]} - TK{record.price} ({record.recorded_at.strftime("%Y-%m-%d")})')
        else:
            self.stdout.write(self.style.WARNING(f'About to delete {count:,} records permanently!'))
            confirm = input('   Type "yes" to confirm deletion: ')
            
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('\nCleanup cancelled'))
                return
            
            self.stdout.write('\nDeleting old records...')
            deleted_count, _ = old_records.delete()
            
            self.stdout.write(self.style.SUCCESS(f'\nSuccessfully deleted {deleted_count:,} old price history records'))
            self.stdout.write(f'   Remaining records: {PriceHistory.objects.count():,}')
            self.stdout.write(self.style.SUCCESS('   Database storage freed up!\n'))
