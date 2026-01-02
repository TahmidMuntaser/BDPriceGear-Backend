from django.core.management.base import BaseCommand
from products.models import Category


class Command(BaseCommand):
    help = 'Update categories to PC component categories'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('\n=== Category Restructure ===\n'))
        
        # Define old categories to remove
        old_categories = ['Microphone', 'Webcam', 'Speaker', 'Headphone', 'Laptop']
        
        # Define new PC component categories
        new_categories = [
            'Processor',
            'Motherboard',
            'RAM',
            'SSD',
            'HDD',
            'Power Supply',
            'Cabinet',
            'GPU',
            'CPU Cooler',
            'Monitor',
            'Keyboard',
            'Mouse',
        ]
        
        # Show current status
        existing = Category.objects.all()
        self.stdout.write('Current categories:')
        for cat in existing:
            self.stdout.write(f'  - {cat.name} ({cat.products.count()} products)')
        
        self.stdout.write(f'\nCategories to remove: {", ".join(old_categories)}')
        self.stdout.write(f'New categories to create: {", ".join(new_categories)}\n')
        
        if not options['confirm']:
            confirm = input('Continue? Type "yes": ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Cancelled'))
                return
        
        # Remove old categories
        removed_count = 0
        for cat_name in old_categories:
            deleted, _ = Category.objects.filter(name=cat_name).delete()
            if deleted > 0:
                removed_count += 1
                self.stdout.write(f'  ✓ Removed: {cat_name}')
        
        # Create new categories
        created_count = 0
        for cat_name in new_categories:
            _, created = Category.objects.get_or_create(
                name=cat_name,
                defaults={'is_active': True}
            )
            if created:
                created_count += 1
                self.stdout.write(f'  ✓ Created: {cat_name}')
            else:
                self.stdout.write(f'  - Exists: {cat_name}')
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Removed {removed_count} old categories'))
        self.stdout.write(self.style.SUCCESS(f'✓ Created {created_count} new categories'))
        self.stdout.write(f'\nTotal categories: {Category.objects.count()}')
