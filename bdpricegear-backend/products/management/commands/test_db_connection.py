"""
Management command to test database connection and configuration
"""

from django.core.management.base import BaseCommand
from django.db import connection, close_old_connections
from django.conf import settings
import time


class Command(BaseCommand):
    help = 'Test database connection and display connection settings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stress-test',
            action='store_true',
            help='Run stress test with multiple connection attempts',
        )
        parser.add_argument(
            '--iterations',
            type=int,
            default=10,
            help='Number of iterations for stress test (default: 10)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Database Connection Test ===\n'))
        
        # Display database settings
        db_settings = settings.DATABASES['default']
        self.stdout.write(self.style.WARNING('Database Configuration:'))
        self.stdout.write(f"  Engine: {db_settings.get('ENGINE', 'N/A')}")
        self.stdout.write(f"  Name: {db_settings.get('NAME', 'N/A')}")
        self.stdout.write(f"  Host: {db_settings.get('HOST', 'N/A')}")
        self.stdout.write(f"  Port: {db_settings.get('PORT', 'N/A')}")
        self.stdout.write(f"  Connection Max Age: {db_settings.get('CONN_MAX_AGE', 'N/A')} seconds")
        self.stdout.write(f"  Connection Health Checks: {db_settings.get('CONN_HEALTH_CHECKS', 'N/A')}")
        
        if 'OPTIONS' in db_settings:
            self.stdout.write(f"  Options: {db_settings['OPTIONS']}")
        
        self.stdout.write('')
        
        # Test connection
        if options['stress_test']:
            self.run_stress_test(options['iterations'])
        else:
            self.run_single_test()

    def run_single_test(self):
        """Run a single connection test"""
        self.stdout.write(self.style.WARNING('Testing database connection...'))
        
        try:
            # Close any existing connections
            close_old_connections()
            
            # Test connection
            start_time = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
                
            elapsed = time.time() - start_time
            
            self.stdout.write(self.style.SUCCESS(f'\n✅ Connection successful! ({elapsed:.3f}s)'))
            self.stdout.write(f'Database version: {version}')
            
            # Test a query
            self.stdout.write(self.style.WARNING('\nTesting product count query...'))
            start_time = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM products_product")
                count = cursor.fetchone()[0]
            elapsed = time.time() - start_time
            
            self.stdout.write(self.style.SUCCESS(f'✅ Query successful! ({elapsed:.3f}s)'))
            self.stdout.write(f'Total products: {count}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Connection failed: {str(e)}'))
            return
        finally:
            close_old_connections()
            
        self.stdout.write(self.style.SUCCESS('\n=== Test Complete ===\n'))

    def run_stress_test(self, iterations):
        """Run multiple connection tests to check for timeouts"""
        self.stdout.write(self.style.WARNING(f'Running stress test with {iterations} iterations...\n'))
        
        successes = 0
        failures = 0
        total_time = 0
        
        for i in range(iterations):
            try:
                # Close old connections before each test
                close_old_connections()
                
                start_time = time.time()
                with connection.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM products_product")
                    count = cursor.fetchone()[0]
                elapsed = time.time() - start_time
                total_time += elapsed
                
                successes += 1
                self.stdout.write(f'  [{i+1}/{iterations}] ✅ Success ({elapsed:.3f}s) - {count} products')
                
                # Small delay between iterations
                time.sleep(0.1)
                
            except Exception as e:
                failures += 1
                self.stdout.write(self.style.ERROR(f'  [{i+1}/{iterations}] ❌ Failed: {str(e)}'))
            finally:
                close_old_connections()
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'\nStress Test Results:'))
        self.stdout.write(f'  Total iterations: {iterations}')
        self.stdout.write(self.style.SUCCESS(f'  Successes: {successes}'))
        if failures > 0:
            self.stdout.write(self.style.ERROR(f'  Failures: {failures}'))
        else:
            self.stdout.write(f'  Failures: {failures}')
        if successes > 0:
            avg_time = total_time / successes
            self.stdout.write(f'  Average time: {avg_time:.3f}s')
        self.stdout.write('\n' + '='*50 + '\n')
