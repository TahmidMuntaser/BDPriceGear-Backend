from django.core.management.base import BaseCommand
from products.models import Category, Product


class Command(BaseCommand):
    help = 'Fix category names - standardize capitalization and remove duplicates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.WARNING('\n=== Category Name Standardization ===\n'))
        
        # Define the correct category names
        correct_categories = {
            'laptop': 'Laptop',
            'mouse': 'Mouse',
            'keyboard': 'Keyboard',
            'monitor': 'Monitor',
            'webcam': 'Webcam',
            'microphone': 'Microphone',
            'speaker': 'Speaker',
            'headphone': 'Headphone',
            'ram': 'RAM',
            'ssd': 'SSD',
            'hdd': 'HDD',
            # Handle possible variations
            'headphones': 'Headphone',
            'speakers': 'Speaker',
            'laptops': 'Laptop',
            'mice': 'Mouse',
            'keyboards': 'Keyboard',
            'monitors': 'Monitor',
            'webcams': 'Webcam',
            'microphones': 'Microphone',
        }
        
        # Get all existing categories
        existing_categories = Category.objects.all()
        
        self.stdout.write(f'Found {existing_categories.count()} categories in database:\n')
        
        fixes_needed = []
        categories_to_delete = []
        
        for category in existing_categories:
            normalized_name = category.name.lower()
            
            if normalized_name in correct_categories:
                correct_name = correct_categories[normalized_name]
                
                if category.name != correct_name:
                    fixes_needed.append((category, correct_name))
                    self.stdout.write(
                        f"  ⚠ '{category.name}' → should be '{correct_name}' "
                        f"({category.products.count()} products)"
                    )
                else:
                    self.stdout.write(
                        f"  ✓ '{category.name}' is correct "
                        f"({category.products.count()} products)"
                    )
            else:
                self.stdout.write(
                    f"  ❌ '{category.name}' is not a standard category "
                    f"({category.products.count()} products)"
                )
        
        if not fixes_needed:
            self.stdout.write(self.style.SUCCESS('\n✓ All category names are correct!'))
            return
        
        self.stdout.write(f'\n{len(fixes_needed)} categories need fixing\n')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
            self.stdout.write('Run without --dry-run to apply fixes\n')
            return
        
        confirm = input('Apply fixes? Type "yes" to confirm: ')
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.ERROR('Cancelled'))
            return
        
        # Apply fixes
        fixed_count = 0
        merged_count = 0
        
        for old_category, correct_name in fixes_needed:
            # Check if correct category already exists
            correct_category = Category.objects.filter(name=correct_name).first()
            
            if correct_category and correct_category != old_category:
                # Merge: Move products to correct category
                products_moved = old_category.products.count()
                old_category.products.all().update(category=correct_category)
                old_category.delete()
                merged_count += 1
                self.stdout.write(
                    f"  ✓ Merged '{old_category.name}' into '{correct_name}' "
                    f"({products_moved} products moved)"
                )
            else:
                # Rename
                old_name = old_category.name
                old_category.name = correct_name
                old_category.slug = None  # Will auto-regenerate on save
                old_category.save()
                fixed_count += 1
                self.stdout.write(
                    f"  ✓ Renamed '{old_name}' → '{correct_name}'"
                )
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Fixed {fixed_count} categories, merged {merged_count} duplicates'
        ))
        self.stdout.write(f'  Total categories now: {Category.objects.count()}')
