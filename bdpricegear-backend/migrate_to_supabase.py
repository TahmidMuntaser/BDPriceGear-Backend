#!/usr/bin/env python
import os
import sys
import subprocess

# Step 1: Export from local SQLite
print("Step 1: Exporting products from local database...")
os.environ.pop('DATABASE_URL', None)
result = subprocess.run([
    sys.executable, 'manage.py', 'dumpdata', 'products'
], capture_output=True, text=True, encoding='utf-8', errors='replace')

if result.returncode != 0:
    print(f"Export failed: {result.stderr}")
    sys.exit(1)

# Save data to file
with open('products_data_clean.json', 'w', encoding='utf-8') as f:
    f.write(result.stdout)

print(f"✓ Exported {len(result.stdout)} characters")

# Step 2: Load into Supabase
print("\nStep 2: Loading into Supabase...")
env = os.environ.copy()
env['DATABASE_URL'] = 'postgresql://postgres.imnfzycseeosuxmaxnfi:bdpricegear%3F123@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres'

result = subprocess.run([
    sys.executable, 'manage.py', 'loaddata', 'products_data_clean.json'
], capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)

print(result.stdout)
if result.stderr:
    print(result.stderr)

if result.returncode != 0:
    print(f"\n✗ Load failed with code {result.returncode}")
    sys.exit(1)

print("✓ Data loaded successfully!")
