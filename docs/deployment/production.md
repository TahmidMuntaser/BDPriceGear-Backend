# Production Deployment Guide

This guide covers deploying BDPriceGear Backend based on your current configuration.

## 🎯 Current Setup Analysis

Your project is **ready for deployment** with:
- ✅ **Render.com** configuration (primary target)
- ✅ **Heroku** compatibility via Procfile  
- ✅ **Static files** handled by WhiteNoise
- ✅ **CORS** configured for frontend domains
- ✅ **All dependencies** included in requirements.txt

## 🚀 Deployment Options

### Option 1: Render.com (Currently Configured)
### Option 2: Heroku (Alternative)
### Option 3: Manual VPS Setup

---

## � Render.com Deployment (Recommended)

Your project is **already configured** for Render with `ALLOWED_HOSTS = ['bdpricegear.onrender.com']`.

### Prerequisites
- Render.com account
- GitHub repository
- Domain (optional)

### Step 1: Your Current Configuration ✅

**Procfile** (already exists):
```
web: gunicorn core.wsgi:application
```

**Dependencies** (already in requirements.txt):
```
gunicorn==23.0.0
whitenoise==6.5.0  
playwright==1.54.0
# ... all other dependencies
```

### Step 2: Environment Variables Setup

Your current `.env` file structure (for development):
```env
SECRET_KEY='your-development-secret-key'
DEBUG=True
```

**For production**, set these environment variables in Render:
```env
SECRET_KEY=your-secure-production-secret-key-here
DEBUG=False
DATABASE_URL=sqlite:///db.sqlite3  # Or PostgreSQL URL
```

### Step 3: Your Current Settings Configuration ✅

Your `settings.py` is **already production-ready**:
```python
# Environment variables loading ✅
SECRET_KEY = os.environ.get("SECRET_KEY", "unsafe-secret-key")
DEBUG = os.environ.get("DEBUG", "False") == "True"

# Render.com domain ✅  
ALLOWED_HOSTS = ['bdpricegear.onrender.com', 'localhost', '127.0.0.1']

# Static files ✅
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# CORS for frontend ✅
CORS_ALLOWED_ORIGINS = [
    "https://bdpricegear.vercel.app",  
    "https://bdpricegear.onrender.com",
    # ... development origins
]
```

### Step 4: Deploy on Render

1. **Connect GitHub Repository**
   - Go to [Render.com](https://render.com)
   - Connect your GitHub account
   - Select `BDPriceGear-Backend` repository

2. **Create Web Service**
   - Service Type: **Web Service**
   - Name: `bdpricegear-backend`
   - Region: Choose closest to your users
   - Branch: `main`
   - Build Command: `pip install -r requirements.txt && playwright install chromium`
   - Start Command: `gunicorn core.wsgi:application` (from your Procfile)

3. **Set Environment Variables**
   ```
   SECRET_KEY=your-new-secure-secret-key
   DEBUG=False
   ```

4. **Deploy**
   - Click "Create Web Service"
   - Render will automatically deploy from your GitHub repo
   - Your API will be available at: `https://bdpricegear-backend.onrender.com`

### Step 5: Database Migration (If Needed)

```bash
# Using Render's console
python bdpricegear-backend/manage.py migrate
python bdpricegear-backend/manage.py collectstatic --noinput
```

---

## 🟣 Heroku Deployment (Alternative)

Your project **already has** Heroku configuration:

### Prerequisites for Heroku
- Heroku CLI
- Heroku account

### Step 1: Heroku Setup

```bash
# Login to Heroku
heroku login

# Create app (update ALLOWED_HOSTS first)
heroku create your-app-name

# Add Playwright buildpack (for web scraping)
heroku buildpacks:add --index 1 https://github.com/mxschmitt/heroku-playwright-buildpack.git
heroku buildpacks:add --index 2 heroku/python

# Set environment variables
heroku config:set SECRET_KEY='your-secure-secret-key'
heroku config:set DEBUG=False

# Deploy
git push heroku main
```



---

## � Production Optimizations

### 1. Current Dependencies Analysis

Your `requirements.txt` includes:
```txt
# Web framework ✅
Django==5.2.5
djangorestframework==3.16.1

# Production server ✅  
gunicorn==23.0.0

# Static files ✅
whitenoise==6.5.0

# Web scraping ✅
playwright==1.54.0
beautifulsoup4==4.13.4
requests==2.32.4

# API docs ✅
drf-yasg==1.21.7

# CORS ✅
django-cors-headers==4.3.1

# Environment ✅
python-dotenv==1.1.1
```

### 2. Production Security (Optional Enhancements)

Your current `settings.py` is production-ready, but you can add these security headers if needed:

```python
# Add to your existing settings.py for enhanced security
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True 
    X_FRAME_OPTIONS = 'DENY'
```



---

## 🔍 Troubleshooting Your Specific Setup

### Common Issues with Your Configuration

1. **Playwright Browsers Missing in Production**
   ```bash
   # Install Chromium in production environment
   playwright install chromium
   playwright install-deps
   ```

2. **CORS Issues with Frontend**
   - Your CORS is configured for:
     - `https://bdpricegear.vercel.app` (production frontend)
     - `https://bdpricegear.onrender.com` (production API)
     - Localhost ports for development
   
   Add new domains to `CORS_ALLOWED_ORIGINS` in settings.py

3. **Static Files Not Loading**
   ```bash
   # Your WhiteNoise config should handle this, but if issues:
   python manage.py collectstatic --noinput
   ```

4. **Long Response Times**
   - Your API scrapes 7 websites, expect 10-20 second responses
   - Use your built-in caching (5-minute cache)
   - Set client timeouts to 30+ seconds

5. **Environment Variables**
   ```bash
   # Check your environment loading
   python -c "import os; print(os.environ.get('DEBUG', 'Not Set'))"
   ```

### Your Specific Performance Characteristics

- **First request**: 10-20 seconds (scraping 7 sites)
- **Cached requests**: < 1 second (5-minute cache)  
- **Memory usage**: ~200-500MB (Playwright browsers)
- **Concurrent requests**: Handle with care (resource intensive)

### Quick Health Check

Test your deployed API:
```bash
# Test the main endpoint
curl "https://your-domain.com/api/price-comparison/?product=mouse"

# Check if all scrapers are working
curl "https://your-domain.com/docs/"  # Should show Swagger UI
```