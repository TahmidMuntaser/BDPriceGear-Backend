from django.core.management.base import BaseCommand
from django.db.models import Count
from products.models import Product, Category, Shop


class Command(BaseCommand):
    help = 'Display product statistics including NULL category counts'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS(' PRODUCT DATABASE STATISTICS'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))
        
        # Total products
        total_products = Product.objects.count()
        available_products = Product.objects.filter(is_available=True).count()
        unavailable_products = Product.objects.filter(is_available=False).count()
        
        self.stdout.write(f'Total Products: {total_products:,}')
        self.stdout.write(f'  ├─ Available: {available_products:,}')
        self.stdout.write(f'  └─ Unavailable: {unavailable_products:,}\n')
        
        # Products with NULL category
        null_category_total = Product.objects.filter(category__isnull=True).count()
        null_category_available = Product.objects.filter(
            category__isnull=True, is_available=True
        ).count()
        null_category_unavailable = Product.objects.filter(
            category__isnull=True, is_available=False
        ).count()
        
        self.stdout.write(self.style.WARNING(f'Products with NULL Category: {null_category_total:,}'))
        self.stdout.write(f'  ├─ Available: {null_category_available:,}')
        self.stdout.write(f'  └─ Unavailable: {null_category_unavailable:,}\n')
        
        # Products WITH category
        with_category_total = Product.objects.filter(category__isnull=False).count()
        with_category_available = Product.objects.filter(
            category__isnull=False, is_available=True
        ).count()
        
        self.stdout.write(self.style.SUCCESS(f'Products with Category: {with_category_total:,}'))
        self.stdout.write(f'  ├─ Available: {with_category_available:,}')
        self.stdout.write(f'  └─ Unavailable: {with_category_total - with_category_available:,}\n')
        
        # Category breakdown
        self.stdout.write(self.style.SUCCESS('\nProducts per Category (available only):'))
        categories = Category.objects.all().order_by('name')
        
        for cat in categories:
            available = cat.products.filter(is_available=True).count()
            total_in_cat = cat.products.count()
            self.stdout.write(f'  {cat.name:15} {available:5,} available ({total_in_cat:,} total)')
        
        # Shop breakdown
        self.stdout.write(self.style.SUCCESS('\nProducts per Shop (available only):'))
        shops = Shop.objects.all().order_by('name')
        
        for shop in shops:
            available = shop.products.filter(is_available=True).count()
            total_in_shop = shop.products.count()
            self.stdout.write(f'  {shop.name:15} {available:5,} available ({total_in_shop:,} total)')
        
        # Validation
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS(' VALIDATION'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))
        
        # Check if counts add up
        category_sum = sum(cat.products.filter(is_available=True).count() for cat in categories)
        
        self.stdout.write(f'Sum of category counts (available): {category_sum:,}')
        self.stdout.write(f'Total available products: {available_products:,}')
        self.stdout.write(f'Products with NULL category (available): {null_category_available:,}')
        self.stdout.write(f'Expected: {category_sum:,} + {null_category_available:,} = {category_sum + null_category_available:,}')
        
        if category_sum + null_category_available == available_products:
            self.stdout.write(self.style.SUCCESS('\n✓ Counts match perfectly!'))
        else:
            self.stdout.write(self.style.ERROR(
                f'\n✗ Mismatch detected! Difference: {available_products - (category_sum + null_category_available):,}'
            ))
        
        # Sample NULL category products
        if null_category_total > 0:
            self.stdout.write(self.style.WARNING(f'\n\nSample products with NULL category (showing first 10):'))
            null_products = Product.objects.filter(category__isnull=True)[:10]
            for i, p in enumerate(null_products, 1):
                status = '✓' if p.is_available else '✗'
                self.stdout.write(f'  {i}. [{status}] {p.name[:70]}... ({p.shop.name})')
        
        self.stdout.write('\n' + '='*80 + '\n')
