"""
Diagnose database connection issues on Render
Run this to identify the root cause of connection timeouts
"""

import os
import sys
import time
import socket
from urllib.parse import urlparse

def check_database_url():
    """Check if DATABASE_URL is configured"""
    print("=" * 60)
    print("DATABASE_URL CONFIGURATION CHECK")
    print("=" * 60)
    
    db_url = os.environ.get('DATABASE_URL')
    
    if not db_url:
        print("❌ DATABASE_URL not set in environment variables!")
        print("   Set it in Render dashboard: Environment > DATABASE_URL")
        return False
    
    print("✅ DATABASE_URL is set")
    
    # Parse URL
    try:
        parsed = urlparse(db_url)
        print(f"\n📊 Database Configuration:")
        print(f"   Protocol: {parsed.scheme}")
        print(f"   Host: {parsed.hostname}")
        print(f"   Port: {parsed.port}")
        print(f"   Database: {parsed.path.lstrip('/')}")
        print(f"   Username: {parsed.username}")
        
        # Check port
        if parsed.port == 6543:
            print(f"\n⚠️  WARNING: Using transaction pooler (port 6543)")
            print(f"   Recommended: Switch to session pooler (port 5432)")
            print(f"   Transaction pooler can cause timeouts on Render")
        elif parsed.port == 5432:
            print(f"\n✅ Using session pooler (port 5432) - Good for Render!")
        else:
            print(f"\n⚠️  Unexpected port: {parsed.port}")
        
        return parsed
    except Exception as e:
        print(f"❌ Error parsing DATABASE_URL: {e}")
        return False


def test_network_connectivity(host, port):
    """Test if we can reach the database server"""
    print("\n" + "=" * 60)
    print("NETWORK CONNECTIVITY TEST")
    print("=" * 60)
    
    print(f"\n🔍 Testing connection to {host}:{port}...")
    
    # Try to resolve hostname
    try:
        ip_address = socket.gethostbyname(host)
        print(f"✅ DNS resolution successful: {host} -> {ip_address}")
    except socket.gaierror as e:
        print(f"❌ DNS resolution failed: {e}")
        print(f"   Cannot resolve hostname: {host}")
        return False
    
    # Try to connect
    attempts = 3
    for i in range(attempts):
        try:
            print(f"\n   Attempt {i+1}/{attempts}...")
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)  # 30 second timeout
            result = sock.connect_ex((host, port))
            elapsed = time.time() - start
            sock.close()
            
            if result == 0:
                print(f"   ✅ TCP connection successful! ({elapsed:.2f}s)")
                return True
            else:
                print(f"   ❌ Connection failed (error code: {result})")
        except socket.timeout:
            print(f"   ❌ Connection timeout after 30 seconds")
        except Exception as e:
            print(f"   ❌ Connection error: {e}")
        
        if i < attempts - 1:
            time.sleep(2)
    
    print(f"\n❌ Failed to connect after {attempts} attempts")
    return False


def test_database_connection():
    """Test actual database connection"""
    print("\n" + "=" * 60)
    print("DATABASE CONNECTION TEST")
    print("=" * 60)
    
    try:
        import psycopg
        from psycopg import OperationalError
        
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            print("❌ DATABASE_URL not set")
            return False
        
        print("\n🔍 Attempting database connection with psycopg...")
        print("   (This may take up to 60 seconds)")
        
        start = time.time()
        try:
            conn = psycopg.connect(
                db_url,
                connect_timeout=60,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10
            )
            elapsed = time.time() - start
            
            # Test query
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            print(f"\n✅ Database connection successful! ({elapsed:.2f}s)")
            print(f"   PostgreSQL version: {version[:50]}...")
            return True
            
        except OperationalError as e:
            elapsed = time.time() - start
            print(f"\n❌ Database connection failed ({elapsed:.2f}s)")
            print(f"   Error: {e}")
            
            error_msg = str(e).lower()
            if 'timeout' in error_msg:
                print("\n🔍 TIMEOUT DETECTED:")
                print("   Possible causes:")
                print("   1. Database server is down or overloaded")
                print("   2. Firewall blocking connection")
                print("   3. IP not whitelisted (if using Supabase/external DB)")
                print("   4. Wrong host/port in DATABASE_URL")
                print("   5. Database taking too long to respond")
            elif 'password' in error_msg or 'authentication' in error_msg:
                print("\n🔍 AUTHENTICATION ERROR:")
                print("   Check username/password in DATABASE_URL")
            elif 'could not connect' in error_msg:
                print("\n🔍 CONNECTION REFUSED:")
                print("   Database server not accepting connections")
                print("   Check if database service is running")
            
            return False
            
    except ImportError:
        print("❌ psycopg not installed")
        print("   Run: pip install psycopg[binary]")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def main():
    print("\n" + "=" * 60)
    print("RENDER DATABASE CONNECTION DIAGNOSTIC")
    print("=" * 60)
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Step 1: Check DATABASE_URL
    parsed = check_database_url()
    if not parsed:
        print("\n❌ Fix DATABASE_URL before proceeding")
        sys.exit(1)
    
    # Step 2: Test network connectivity
    if parsed.hostname and parsed.port:
        network_ok = test_network_connectivity(parsed.hostname, parsed.port)
        if not network_ok:
            print("\n❌ NETWORK ISSUE DETECTED")
            print("\nPossible solutions:")
            print("1. Check if database server is running")
            print("2. Verify firewall rules allow connections from Render")
            print("3. If using Supabase: Add Render's IP to allowed list")
            print("4. Check database provider status page")
            print("\n⚠️  Skipping database connection test due to network failure")
            sys.exit(1)
    
    # Step 3: Test database connection
    db_ok = test_database_connection()
    
    # Summary
    print("\n" + "=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)
    
    if db_ok:
        print("\n✅ ALL TESTS PASSED!")
        print("   Your database connection is working correctly.")
        print("   If you're still seeing errors, they may be intermittent.")
    else:
        print("\n❌ DATABASE CONNECTION FAILED")
        print("\nNext steps:")
        print("1. Check Render logs for more details")
        print("2. Verify DATABASE_URL in Render dashboard")
        print("3. Test connection from Render shell:")
        print("   render shell")
        print("   python bdpricegear-backend/diagnose_db.py")
        print("4. Contact database provider support")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
