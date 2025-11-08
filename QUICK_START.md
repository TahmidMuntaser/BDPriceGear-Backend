# 🚀 Quick Start - Your API is LIVE!

## ✅ Everything is Ready!

Your product catalog API is now **live on Render** and will **automatically update every hour**.

## See It Working Right Now

### 1️⃣ View Products
```
https://bdpricegear.onrender.com/api/products/?limit=5
```
Shows 5 latest products with prices from all 7 shops

### 2️⃣ View Specific Category
```
https://bdpricegear.onrender.com/api/products/?category=laptop&limit=10
```
Shows 10 laptops sorted by price

### 3️⃣ Search by Shop
```
https://bdpricegear.onrender.com/api/products/?shop=startech&limit=10
```
Shows StarTech products

### 4️⃣ Check System Health
```
https://bdpricegear.onrender.com/api/health/
```
Response:
```json
{
  "status": "ok",
  "service": "BDPriceGear Backend",
  "database": "connected",
  "products_in_db": 1417,
  "timestamp": "2025-11-09T15:30:45Z"
}
```

## 📊 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/products/` | GET | List all products (paginated) |
| `/api/products/?category=laptop` | GET | Filter by category |
| `/api/products/?shop=startech` | GET | Filter by shop |
| `/api/categories/` | GET | List all categories |
| `/api/shops/` | GET | List all shops |
| `/api/health/` | GET | System health check |
| `/api/update/` | GET | Check last update time |
| `/api/update/` | POST | Trigger manual update |

## 📈 Current Catalog Stats

- **Total Products:** 1,417 ✅
- **Shops:** 7 (StarTech, Ryans, Skyland, PC House, UltraTech, Binary, PotakaIT)
- **Categories:** 11 (Laptop, Mouse, Keyboard, Monitor, etc.)
- **Update Frequency:** Every hour
- **Database:** Supabase PostgreSQL
- **Hosting:** Render (https://bdpricegear.onrender.com)

## 🔄 Automatic Updates

**Every hour at minute 0** (1:00 AM, 2:00 AM, 3:00 AM, etc.):
1. APScheduler service wakes up
2. Scrapes latest products from 7 shops
3. Updates Supabase database
4. API serves new data immediately

**No manual intervention needed!** ✨

## 🎛️ Manual Controls

### Trigger Update Now
```bash
curl -X POST https://bdpricegear.onrender.com/api/update/
```

### Check Last Update
```bash
curl https://bdpricegear.onrender.com/api/update/
```

### View All Products (Paginated)
```bash
curl "https://bdpricegear.onrender.com/api/products/?page=1&limit=20"
```

## 📱 Example Frontend Integration

### React/Vue Example
```javascript
// Fetch latest products
fetch('https://bdpricegear.onrender.com/api/products/?limit=10')
  .then(r => r.json())
  .then(data => console.log(data.results))

// Response:
{
  "count": 1417,
  "next": "https://...",
  "results": [
    {
      "id": 1,
      "name": "Laptop Name",
      "current_price": "50000.00",
      "currency": "BDT",
      "shop": "StarTech",
      "image_url": "https://...",
      "product_url": "https://..."
    }
  ]
}
```

## 🔍 Filter Products

```bash
# By price range (not directly supported, but you can filter in frontend)
GET /api/products/?limit=100  # Get all and filter

# By category
GET /api/products/?category=laptop

# By shop
GET /api/products/?shop=startech

# Combine filters
GET /api/products/?category=monitor&shop=ryans&limit=10

# Pagination
GET /api/products/?page=2&limit=20
```

## 📊 Available Categories

- Laptop
- Mouse
- Keyboard
- Monitor
- Headphone
- Speaker
- Webcam
- Microphone
- RAM
- SSD
- HDD

## 🏪 Available Shops

1. StarTech (startech)
2. Ryans (ryans)
3. SkyLand (skyland)
4. PC House (pchouse)
5. UltraTech (ultratech)
6. Binary (binary)
7. PotakaIT (potakait)

## ⚙️ Want to Customize?

### Change Update Frequency
Edit `update_products_hourly.py`:
- Change cron schedule
- Change product limit per shop
- Add/remove shops

### Change Product Limit
More products per update = slower but more data:
```python
call_command('populate_products', limit=50)  # Default is 10
```

### Disable Hourly Updates
Remove `scheduler:` line from `Procfile` and redeploy

## 📞 Support

### Check Logs
Render Dashboard → Service → Logs

### Debug Endpoint
```bash
curl https://bdpricegear.onrender.com/api/health/
```

### Manual Test
```bash
# This will update now
curl -X POST https://bdpricegear.onrender.com/api/update/
```

## 🎓 Learn More

- Full docs: `HOURLY_UPDATES_SETUP.md`
- Architecture: `DEPLOYMENT_READY.md`
- Code: `https://github.com/TahmidMuntaser/BDPriceGear-Backend`

---

## 🎉 You're All Set!

Your API is:
- ✅ Live on Render
- ✅ Connected to Supabase PostgreSQL
- ✅ Updating hourly automatically
- ✅ Serving 1,417 products
- ✅ Ready for production

**Start using it now!**

```
https://bdpricegear.onrender.com/api/products/
```
