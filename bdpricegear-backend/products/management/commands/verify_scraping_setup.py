"""
Management command to verify scraping setup and test the cache
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db import connection
import sys


class Command(BaseCommand):
    help = 'Verify scraping setup (cache, database, permissions)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== BDPriceGear Scraping Setup Verification ===\n'))
        
        all_good = True
        
        # 1. Check Cache
        self.stdout.write('1. Checking Cache Configuration...')
        try:
            # Try to set and get a test value
            test_key = 'setup_test_key'
            test_value = 'test_value_123'
            cache.set(test_key, test_value, timeout=60)
            retrieved = cache.get(test_key)
            
            if retrieved == test_value:
                self.stdout.write(self.style.SUCCESS('   ✅ Cache is working correctly'))
                cache.delete(test_key)
            else:
                self.stdout.write(self.style.ERROR('   ❌ Cache read/write test failed'))
                self.stdout.write(self.style.WARNING('   Run: python manage.py createcachetable'))
                all_good = False
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Cache error: {str(e)}'))
            self.stdout.write(self.style.WARNING('   Run: python manage.py createcachetable'))
            all_good = False
        
        self.stdout.write('')
        
        # 2. Check Database
        self.stdout.write('2. Checking Database Connection...')
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM products_product")
                count = cursor.fetchone()[0]
                self.stdout.write(self.style.SUCCESS(f'   ✅ Database connected ({count} products in database)'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Database error: {str(e)}'))
            all_good = False
        
        self.stdout.write('')
        
        # 3. Check Cache Table Exists
        self.stdout.write('3. Checking Cache Table...')
        try:
            # Detect database backend and use appropriate query
            db_vendor = connection.vendor
            
            with connection.cursor() as cursor:
                if db_vendor == 'postgresql':
                    # PostgreSQL query
                    cursor.execute("""
                        SELECT tablename FROM pg_tables 
                        WHERE schemaname = 'public' AND tablename = 'django_cache_table'
                    """)
                elif db_vendor == 'sqlite':
                    # SQLite query
                    cursor.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name='django_cache_table'
                    """)
                elif db_vendor == 'mysql':
                    # MySQL query
                    cursor.execute("""
                        SELECT TABLE_NAME FROM information_schema.TABLES
                        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'django_cache_table'
                    """)
                else:
                    # Fallback: try to query the table directly
                    cursor.execute("SELECT COUNT(*) FROM django_cache_table")
                    self.stdout.write(self.style.SUCCESS(f'   ✅ django_cache_table exists ({db_vendor})'))
                    raise StopIteration  # Skip to next section
                
                result = cursor.fetchone()
                
                if result and result[0]:
                    self.stdout.write(self.style.SUCCESS(f'   ✅ django_cache_table exists ({db_vendor})'))
                else:
                    self.stdout.write(self.style.ERROR('   ❌ django_cache_table not found'))
                    self.stdout.write(self.style.WARNING('   Run: python manage.py createcachetable'))
                    all_good = False
        except StopIteration:
            # Already reported success, continue
            pass
        except Exception as e:
            # Try direct query as fallback
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM django_cache_table LIMIT 1")
                    self.stdout.write(self.style.SUCCESS('   ✅ django_cache_table exists'))
            except Exception as e2:
                self.stdout.write(self.style.ERROR('   ❌ django_cache_table not found'))
                self.stdout.write(self.style.WARNING(f'   Error: {str(e2)}'))
                self.stdout.write(self.style.WARNING('   Run: python manage.py createcachetable'))
                all_good = False
        
        self.stdout.write('')
        
        # 4. Check Shops
        self.stdout.write('4. Checking Shops Configuration...')
        try:
            from products.models import Shop
            shops = Shop.objects.filter(is_active=True, scraping_enabled=True)
            shop_count = shops.count()
            
            if shop_count > 0:
                self.stdout.write(self.style.SUCCESS(f'   ✅ {shop_count} active shops configured'))
                for shop in shops:
                    self.stdout.write(f'      - {shop.name}')
            else:
                self.stdout.write(self.style.WARNING('   ⚠️  No active shops found'))
                self.stdout.write(self.style.WARNING('   Shops will be created on first scrape'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Error checking shops: {str(e)}'))
            all_good = False
        
        self.stdout.write('')
        
        # 5. Check Categories
        self.stdout.write('5. Checking Categories Configuration...')
        try:
            from products.models import Category
            categories = Category.objects.filter(is_active=True)
            cat_count = categories.count()
            
            if cat_count > 0:
                self.stdout.write(self.style.SUCCESS(f'   ✅ {cat_count} active categories'))
                for cat in categories:
                    self.stdout.write(f'      - {cat.name}')
            else:
                self.stdout.write(self.style.WARNING('   ⚠️  No categories found'))
                self.stdout.write(self.style.WARNING('   Categories will be created on first scrape'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Error checking categories: {str(e)}'))
            all_good = False
        
        self.stdout.write('')
        
        # 6. Check if update is currently in progress
        self.stdout.write('6. Checking Scraping Status...')
        try:
            update_in_progress = cache.get('update_in_progress', False)
            last_error = cache.get('last_scraping_error', None)
            
            if update_in_progress:
                self.stdout.write(self.style.WARNING('   ⚠️  Scraping is currently in progress'))
            else:
                self.stdout.write(self.style.SUCCESS('   ✅ No scraping in progress'))
            
            if last_error:
                self.stdout.write(self.style.WARNING(f'   ⚠️  Last error: {last_error[:100]}...'))
                self.stdout.write(self.style.WARNING('   Clear with: cache.delete("last_scraping_error")'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ❌ Error checking status: {str(e)}'))
            all_good = False
        
        self.stdout.write('')
        self.stdout.write('='*50)
        
        if all_good:
            self.stdout.write(self.style.SUCCESS('\n✅ ALL CHECKS PASSED!\n'))
            self.stdout.write('You can now trigger scraping:')
            self.stdout.write('  - API: curl -X POST http://localhost:8000/api/update/')
            self.stdout.write('  - CLI: python manage.py populate_catalog')
        else:
            self.stdout.write(self.style.ERROR('\n❌ SOME CHECKS FAILED\n'))
            self.stdout.write('Please fix the issues above before running scraping.')
            sys.exit(1)
        
        self.stdout.write('')
