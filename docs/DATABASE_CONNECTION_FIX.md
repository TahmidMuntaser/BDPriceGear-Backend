# Database Connection Timeout Fix

This document explains the fixes implemented to resolve the "connection timeout expired" errors in the BDPriceGear Backend application.

## Problem

The application was experiencing intermittent database connection timeouts with the error:
```
"database": "error: connection timeout expired"
```

## Root Causes Identified

1. **Stale database connections** - Connections were not being properly closed/recycled
2. **Connection pooling misconfiguration** - Incorrect settings for Supabase poolers
3. **No connection cleanup middleware** - Connections lingered after requests
4. **Long-running operations** - Scraping tasks blocking database connections
5. **Worker process issues** - Gunicorn workers not recycling properly

## Fixes Implemented

### 1. Database Connection Middleware

Created `core/middleware/database.py` to:
- Close old/stale connections before each request
- Clean up connections after each response
- Handle connection errors gracefully
- Prevent connection pool exhaustion

**File**: `bdpricegear-backend/core/middleware/database.py`

### 2. Improved Database Configuration

Updated `settings.py` with:
- **Increased connection timeout**: 15 seconds (from 10)
- **Longer conn_max_age**: 600 seconds (10 minutes) for session pooler
- **Better keepalive settings**: 30s idle, 10s interval, 5 retries
- **Idle transaction timeout**: 60 seconds to prevent stuck connections
- **Statement timeout**: 300 seconds (5 minutes) for long operations
- **Connection health checks**: Enabled for session pooler

**File**: `bdpricegear-backend/core/settings.py`

### 3. Connection Cleanup in Views

Updated all views to:
- Call `close_old_connections()` before database operations
- Use `finally` blocks to ensure cleanup
- Close connections in background threads

**Files affected**:
- `bdpricegear-backend/products/views.py`

### 4. Gunicorn Worker Optimization

Created `gunicorn_config.py` with:
- **Worker recycling**: `max_requests=1000` to prevent memory leaks
- **Graceful shutdown**: 30-second timeout
- **Connection cleanup hooks**: Close DB connections on worker init/exit
- **Better logging**: Track worker lifecycle

**File**: `bdpricegear-backend/gunicorn_config.py`

### 5. Database Connection Testing

Created management command to test connections:
```bash
python manage.py test_db_connection
python manage.py test_db_connection --stress-test --iterations 20
```

**File**: `bdpricegear-backend/products/management/commands/test_db_connection.py`

## Configuration Differences

### Transaction Pooler (Port 6543) - Serverless
```python
CONN_MAX_AGE = 0  # Close after each request
CONN_HEALTH_CHECKS = False
DISABLE_SERVER_SIDE_CURSORS = True
connect_timeout = 15
```

### Session Pooler (Port 5432) - Recommended for Render/Railway
```python
CONN_MAX_AGE = 600  # Keep alive 10 minutes
CONN_HEALTH_CHECKS = True
keepalives = 1
keepalives_idle = 30
keepalives_interval = 10
keepalives_count = 5
connect_timeout = 15
```

## Deployment

### Environment Variables Required

```bash
# Required
DATABASE_URL=postgresql://user:password@host:5432/database

# Optional
DEBUG=False
SECRET_KEY=your-secret-key
PORT=8000
```

### Starting the Server

The application now uses the gunicorn config file:

**Railway/Render**:
```bash
./start.sh
```

**Local Development**:
```bash
cd bdpricegear-backend
gunicorn core.wsgi:application --config gunicorn_config.py
```

## Testing the Fixes

### 1. Test Basic Connection
```bash
cd bdpricegear-backend
python manage.py test_db_connection
```

### 2. Stress Test (20 iterations)
```bash
python manage.py test_db_connection --stress-test --iterations 20
```

### 3. Monitor Health Endpoint
```bash
curl https://your-domain.com/api/health/
```

Should return:
```json
{
  "status": "ok",
  "database": "connected",
  "products_in_db": 1234,
  "last_update": "2026-01-03 10:30 AM +06"
}
```

## Monitoring

### Key Metrics to Watch

1. **Database connection count** - Should not exceed pool size
2. **Response times** - Should be consistent, no timeouts
3. **Worker restarts** - Should restart after 1000 requests
4. **Error logs** - Watch for connection timeout errors

### Logs to Check

```bash
# Connection errors
grep "connection timeout" logs/

# Worker lifecycle
grep "Worker spawned\|Worker exiting" logs/

# Database queries
grep "Database query failed" logs/
```

## Best Practices Going Forward

1. **Always use the middleware** - Don't remove `DatabaseConnectionMiddleware`
2. **Close connections in threads** - Call `close_old_connections()` in background tasks
3. **Use session pooler** - Port 5432 is better for long-running servers
4. **Monitor connection pool** - Check database connection count regularly
5. **Recycle workers** - Let gunicorn restart workers to prevent leaks
6. **Test before deploying** - Run stress tests after major changes

## Troubleshooting

### Still seeing timeouts?

1. **Check DATABASE_URL port**:
   - Port 6543 = Transaction pooler (for serverless)
   - Port 5432 = Session pooler (recommended)

2. **Increase timeouts** in `settings.py`:
   ```python
   'connect_timeout': 20,  # Increase to 20
   'options': '-c statement_timeout=600000',  # 10 minutes
   ```

3. **Reduce conn_max_age** if using transaction pooler:
   ```python
   conn_max_age=0  # Must be 0 for port 6543
   ```

4. **Check worker count**:
   - Too many workers = connection pool exhaustion
   - Recommended: 2-4 workers for most deployments

5. **Verify middleware is active**:
   ```python
   # In settings.py MIDDLEWARE list
   'core.middleware.database.DatabaseConnectionMiddleware'
   ```

### Connection Pool Exhausted?

Your database has a maximum connection limit. If you see "too many connections":

1. **Reduce worker count** in `gunicorn_config.py`
2. **Lower conn_max_age** to close connections faster
3. **Upgrade database plan** for more connections

## Summary

The connection timeout issue has been resolved by:
- ✅ Adding database connection cleanup middleware
- ✅ Optimizing database connection settings
- ✅ Improving gunicorn worker management
- ✅ Adding connection health checks
- ✅ Implementing proper connection cleanup in views
- ✅ Creating monitoring and testing tools

The application should now handle database connections reliably without timeouts.
