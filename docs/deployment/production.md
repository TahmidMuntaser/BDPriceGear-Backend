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

## 🔧 Manual VPS Deployment

### Prerequisites
- Ubuntu 20.04+ server  
- Domain name (optional)
- SSH access

### Step 1: Server Setup (Install Dependencies)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python, Node.js (for Playwright), and Nginx
sudo apt install python3 python3-pip python3-venv nginx -y
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

### Step 2: Deploy Your Project

```bash
# Create app user and directory
sudo adduser bdpricegear
su - bdpricegear
mkdir ~/app && cd ~/app

# Clone your repository
git clone https://github.com/TahmidMuntaser/BDPriceGear-Backend.git .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install your actual dependencies
pip install -r requirements.txt

# Install Playwright browsers (for your scrapers)
playwright install chromium
```

### Step 3: Configure Environment

Create production `.env` file:
```env
SECRET_KEY=your-secure-secret-key-here
DEBUG=False
# Add your domain to ALLOWED_HOSTS in settings.py
```

Update `ALLOWED_HOSTS` in `bdpricegear-backend/core/settings.py`:
```python
ALLOWED_HOSTS = ['your-domain.com', 'bdpricegear.onrender.com', 'localhost']
```

### Step 4: Prepare Django Application

```bash
# Navigate to Django project
cd bdpricegear-backend

# Collect static files (using your WhiteNoise config)
python manage.py collectstatic --noinput

# Apply database migrations
python manage.py migrate

# Test the application
python manage.py check --deploy
```

### Step 5: Configure Gunicorn Service

Create `/etc/systemd/system/bdpricegear.service`:
```ini
[Unit]
Description=BDPriceGear API
After=network.target

[Service]
User=bdpricegear
Group=www-data
WorkingDirectory=/home/bdpricegear/app/bdpricegear-backend
Environment="PATH=/home/bdpricegear/app/venv/bin"
ExecStart=/home/bdpricegear/app/venv/bin/gunicorn --workers 3 --bind unix:/home/bdpricegear/app/bdpricegear.sock core.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Start the service
sudo systemctl daemon-reload
sudo systemctl start bdpricegear
sudo systemctl enable bdpricegear
sudo systemctl status bdpricegear  # Check if running
```

### Step 6: Configure Nginx Reverse Proxy

Create `/etc/nginx/sites-available/bdpricegear`:
```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    # Static files served by WhiteNoise, but we can cache them at Nginx level
    location /static/ {
        proxy_pass http://unix:/home/bdpricegear/app/bdpricegear.sock;
        proxy_cache_valid 200 1d;
        add_header Cache-Control "public, max-age=86400";
    }

    # API requests with longer timeouts (for web scraping)
    location / {
        include proxy_params;
        proxy_pass http://unix:/home/bdpricegear/app/bdpricegear.sock;
        proxy_read_timeout 120s;    # Allow time for scraping
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
    }
}
```

```bash
# Enable site and restart Nginx
sudo ln -s /etc/nginx/sites-available/bdpricegear /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
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

### 2. Environment-Specific Settings

Create `bdpricegear-backend/core/settings_prod.py` for additional production settings:
```python
from .settings import *

# Override for production
if not DEBUG:
    # Security headers
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True 
    X_FRAME_OPTIONS = 'DENY'
    
    # Force HTTPS in production
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    
    # Logging
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'file': {
                'level': 'INFO',
                'class': 'logging.FileHandler',
                'filename': 'bdpricegear.log',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['file'],
                'level': 'INFO',
                'propagate': True,
            },
            'products.views': {
                'handlers': ['file'],
                'level': 'INFO',
                'propagate': True,
            },
        },
    }
```

### 3. SSL Certificate (Let's Encrypt)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal (already handles renewal)
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
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

### Your Specific Dependencies Issues

If Playwright fails to install:
```bash
# Manual installation
wget -q -O - https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
sudo apt-get install chromium-browser
export PLAYWRIGHT_BROWSERS_PATH=/usr/bin/chromium-browser
```

### Performance Monitoring

Your API characteristics:
- **Cold start**: 15-20 seconds (first request)
- **Cached requests**: < 1 second  
- **Memory usage**: ~200-500MB (with Playwright)
- **CPU usage**: High during scraping

### Health Check for Your API

Add to `products/views.py`:
```python
@api_view(['GET'])
def health_check(request):
    return Response({
        'status': 'healthy',
        'scrapers': ['StarTech', 'Ryans', 'SkyLand', 'PcHouse', 'UltraTech', 'Binary', 'PotakaIT'],
        'cache_enabled': True,
        'playwright_ready': True
    })
```

Add to `products/urls.py`:
```python
path('health/', health_check, name='health-check'),
```

Then monitor: `https://your-domain.com/api/health/`