# Hourly Product Updates - Setup Guide

## Overview
This system automatically updates product data from Bangladesh e-commerce sites **every hour** and displays it on your Render site at **https://bdpricegear.onrender.com/**

## How It Works

### Architecture
```
┌─────────────────────────────────────────────────────────┐
│                   Render (Production)                    │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  1. Web Service (API)                                     │
│     └─ Django + DRF                                       │
│     └─ Serves products at /api/products/                 │
│                                                           │
│  2. Scheduler Service (Separate Process)                 │
│     └─ APScheduler                                       │
│     └─ Runs every hour                                   │
│     └─ Updates products in Supabase                      │
│                                                           │
│  3. Database (Supabase PostgreSQL)                       │
│     └─ Stores product catalog                            │
│     └─ 1,417 products, 11 categories, 7 shops           │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

## Deployment on Render

### Step 1: Update Environment Variables
Add these to your Render service settings:

```
DATABASE_URL=postgresql://username:password@host:port/database
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=False
ALLOWED_HOSTS=bdpricegear.onrender.com
```

### Step 2: Deploy to Render
```bash
git add .
git commit -m "Add hourly product updates with APScheduler"
git push
```

Render will:
1. Install dependencies (including APScheduler)
2. Run migrations
3. Start the web service (`gunicorn`)
4. Start the scheduler service (APScheduler)

### Step 3: Verify It's Working

**Check the API is serving data:**
```
GET https://bdpricegear.onrender.com/api/products/?limit=5
```

**Check the health status:**
```
GET https://bdpricegear.onrender.com/api/health/
```

**Manually trigger an update:**
```
POST https://bdpricegear.onrender.com/api/update/
```

**Check update status:**
```
GET https://bdpricegear.onrender.com/api/update/
```

## How Updates Work

### Automatic (Hourly)
- **When:** Every hour at minute 0 (1:00 AM, 2:00 AM, etc.)
- **What:** Scrapes 10 products per shop
- **Where:** Updates Supabase PostgreSQL
- **View Results:** https://bdpricegear.onrender.com/api/products/

### Manual (On-Demand)
```bash
# Local - Trigger immediate update
curl -X POST https://bdpricegear.onrender.com/api/update/

# Response:
{
  "status": "success",
  "message": "✅ Product update completed",
  "timestamp": "2025-11-09T15:30:45Z",
  "products_updated": 1450
}
```

## Local Development

### Run the scheduler locally
```bash
# Install dependencies
pip install -r requirements.txt

# Run the scheduler
python update_products_hourly.py
```

This will start the scheduler and update products every hour locally.

### Manual update
```bash
cd bdpricegear-backend
python manage.py populate_products --limit 10
```

## Updating Product Count

To scrape more products, edit `update_products_hourly.py`:

```python
# Change this line:
call_command('populate_products', limit=10)

# To scrape more per shop:
call_command('populate_products', limit=50)  # 50 products per shop
```

Then redeploy:
```bash
git add update_products_hourly.py
git commit -m "Update product limit to 50"
git push
```

## Monitoring

### Logs on Render
Check logs in Render dashboard:
1. Go to your service
2. Click "Logs"
3. Look for "🔄 Starting hourly product update..."

### View Update History
```python
# Get last update time from cache
curl https://bdpricegear.onrender.com/api/update/
```

## Troubleshooting

### No updates happening?
1. Check Render logs for errors
2. Verify `scheduler:` line in Procfile exists
3. Restart the service in Render dashboard

### Updates not showing in API?
1. Check database connection: `GET /api/health/`
2. Verify products are in Supabase: `SELECT COUNT(*) FROM products_product`
3. Clear cache: Restart the service

### Scheduler won't start?
1. Install APScheduler: `pip install APScheduler==3.10.4`
2. Check that `update_products_hourly.py` is in project root
3. Verify DJANGO_SETTINGS_MODULE is set correctly

## File Structure
```
BDPriceGear-Backend/
├── Procfile                          # Updated: added scheduler service
├── requirements.txt                  # Updated: added APScheduler
├── update_products_hourly.py         # NEW: Scheduler script
├── bdpricegear-backend/
│   ├── products/
│   │   ├── views.py                 # Updated: added trigger_update endpoint
│   │   └── urls.py                  # Updated: added update URL
│   └── ...
└── .github/
    └── workflows/
        ├── scrape-hourly.yml        # OLD: Disabled (Playwright issues)
        └── populate-database.yml    # OLD: Disabled (Playwright issues)
```

## Performance Notes
- **Scraping 10 products/shop:** ~2-3 minutes per update
- **Database:** Supabase handles concurrent updates well
- **API Response:** Data served from cache (< 100ms)
- **No downtime:** Updates happen in background

## Next Steps
1. Deploy this code to Render
2. Monitor first few updates in logs
3. Adjust product limit as needed
4. Set up monitoring/alerts if desired

## Support
- Check logs: Render Dashboard → Service → Logs
- Test manually: `POST /api/update/`
- Monitor status: `GET /api/health/`
