# Installation Guide

## Prerequisites

- **Python**: 3.8+ (## Step 6: Run Development Server

```bash
python manage.py runserver
```

The API will be available at: `http://127.0.0.1:8000/`

## Step 7: Test the API

### Quick Test:
- **Root URL**: `http://127.0.0.1:8000/` (redirects to API)
- **API Endpoint**: `http://127.0.0.1:8000/api/price-comparison/?product=mouse`
- **API Documentation**: `http://127.0.0.1:8000/docs/` (Swagger UI)

### Test Scraping:
```bash
# Test with a real product search (takes 10-20 seconds)
curl "http://127.0.0.1:8000/api/price-comparison/?product=laptop"
```
- **Git**: For cloning the repository
- **Virtual Environment**: venv (recommended)
- **Chrome/Chromium**: Auto-installed by Playwright
- **Node.js**: Auto-installed by Playwright (for browser automation)

## Step 1: Clone Repository

```bash
git clone https://github.com/TahmidMuntaser/BDPriceGear-Backend.git
cd bdpricegear-backend
```

## Step 2: Create Virtual Environment

### Using venv (Recommended)
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### Using conda
```bash
conda create -n bdpricegear python=3.10
conda activate bdpricegear
```

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 4: Install Playwright Browsers

```bash
# Install only Chromium (used by your scrapers)
playwright install chromium

# Install system dependencies for Playwright
playwright install-deps
```

## Step 5: Setup Django Application

```bash
cd bdpricegear-backend

# Apply database migrations (minimal, no custom models)
python manage.py migrate

# Create superuser (optional - for admin access)
python manage.py createsuperuser
```

## Step 7: Run Development Server

```bash
python manage.py runserver
```

The API will be available at: `http://127.0.0.1:8000/`

## Step 8: Test the API

Visit the Swagger documentation:
```
http://127.0.0.1:8000/docs/
```

Or test the endpoint directly:
```
http://127.0.0.1:8000/api/price-comparison/?product=mouse&limit=5
```

## Troubleshooting

### Common Issues

#### 1. Playwright Installation Issues
```bash
# Fix Playwright installation
playwright install --with-deps chromium
```

#### 2. Python Version Issues
Make sure you're using Python 3.8+:
```bash
python --version
```

#### 3. Module Not Found Errors
Ensure virtual environment is activated and dependencies are installed:
```bash
pip list | grep django
```

#### 4. Port Already in Use
Change the port:
```bash
python manage.py runserver 8080
```

### Environment Variables

Your project uses a `.env` file in the **root directory** (not in bdpricegear-backend/):
```env
SECRET_KEY=your-secure-secret-key
DEBUG=True
```

The project automatically loads this with `python-dotenv`.

### Performance Tips for Your Setup

1. **Stable internet connection** - Essential for scraping 7 e-commerce sites
2. **Sufficient RAM** - Minimum 4GB (Playwright browsers are memory-intensive)  
3. **SSD storage** - For faster SQLite database operations
4. **Patient testing** - First API calls take 10-20 seconds (web scraping)
5. **Use caching** - Subsequent identical queries return instantly (5-min cache)

## Next Steps

- [Development Workflow](development.md)
- [API Usage Examples](../api/examples.md)
- [Deployment Guide](../deployment/production.md)