# Contribution Guidelines

Thank you for your interest in contributing to BDPriceGear Backend! This document provides guidelines for contributing to the project.

## 🚀 Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Create a branch** for your feature or bugfix
4. **Make your changes** following our coding standards
5. **Test your changes** thoroughly
6. **Submit a pull request**

## 📝 Development Workflow

### 1. Set Up Development Environment

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/BDPriceGear-Backend.git
cd BDPriceGear-Backend

# Add upstream remote
git remote add upstream https://github.com/TahmidMuntaser/BDPriceGear-Backend.git

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
playwright install chromium
```

### 2. Create Feature Branch

```bash
# Update your main branch
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/your-feature-name
```

### 3. Make Changes

Follow Django best practices and make your changes in the appropriate files:
- **Scrapers**: `products/scraper.py`
- **API Views**: `products/views.py` 
- **URL Routes**: `products/urls.py`
- **Settings**: `core/settings.py`

### 4. Test Your Changes

```bash
# Currently no automated tests - test manually
python manage.py runserver

# Test the API endpoint
curl "http://127.0.0.1:8000/api/price-comparison/?product=test"

# Check Django admin
python manage.py check
```

### 5. Commit and Push

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "Add: New feature description"

# Push to your fork
git push origin feature/your-feature-name
```

### 6. Create Pull Request

1. Go to GitHub and create a pull request
2. Fill out the PR template
3. Wait for review and address feedback

## 🎯 Types of Contributions

### 🐛 Bug Fixes
- Fix scraping issues for specific sites
- Resolve API errors
- Performance improvements
- Documentation fixes

### ✨ New Features
- **Add new e-commerce site scrapers** (main contribution area)
- **Improve caching system** (currently simple in-memory)
- **Add response filtering/sorting**
- **Performance optimizations**
- **Error handling improvements**

### 📚 Documentation
- **Scraper documentation** for new sites
- **API usage examples**
- **Deployment guides**
- **Code comments in scraper.py**

### 🧪 Testing (Currently Missing - Great Contribution Area!)
- **Unit tests for scrapers**
- **API endpoint tests** 
- **Mock scraping tests**
- **Performance/load tests**

## 🏷️ Commit Message Guidelines

Use conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

### Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples:
```
feat(scraper): add support for TechLand e-commerce site

fix(api): handle timeout errors in price comparison endpoint

docs(api): update endpoint documentation with new parameters

test(scraper): add unit tests for StarTech scraper
```

## 🧪 Testing Guidelines

### Testing (Currently No Tests - Help Needed!)
```bash
# Currently no tests exist - this is a great contribution opportunity!
python manage.py test  # Returns: Ran 0 tests

# Manual testing approach:
python manage.py runserver
# Test API manually at http://127.0.0.1:8000/api/price-comparison/?product=mouse

# Suggested test setup for contributors:
pip install coverage pytest-django
```

### Writing Tests (Great Contribution Opportunity!)

**Current Status**: No tests exist - this is a priority area for contributors!

**Suggested Test Structure**:
```python
# products/tests.py (currently empty)
from django.test import TestCase
from unittest.mock import patch, Mock
from products.scraper import scrape_startech
from products.views import price_comparison

class ScraperTestCase(TestCase):
    @patch('products.scraper.requests.get')
    def test_scrape_startech_success(self, mock_get):
        # Mock the HTTP response
        mock_response = Mock()
        mock_response.text = '<html>mock product data</html>'
        mock_get.return_value = mock_response
        
        result = scrape_startech("laptop")
        self.assertIn("products", result)
        self.assertIn("logo", result)
        
    def test_api_endpoint_requires_product(self):
        response = self.client.get('/api/price-comparison/')
        self.assertEqual(response.status_code, 400)
```

**Test Areas Needed**:
- Scraper function tests (with mocked HTTP responses)
- API endpoint tests
- Error handling tests
- Cache functionality tests

## 🛠️ Adding New E-commerce Scrapers

### 1. Create Scraper Function

```python
def scrape_newsite(product):
    """Scrape products from NewSite e-commerce"""
    try:
        url = f"https://newsite.com/search?q={urllib.parse.quote(product)}"
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        
        products = []
        # Implement scraping logic
        
        return {
            "products": products,
            "logo": "https://newsite.com/logo.png"
        }
    except Exception as e:
        logger.error(f"NewSite scraper error: {e}")
        return {"products": [], "logo": "logo not found"}
```

### 2. Add to Views

Update `products/views.py` to include your scraper in the appropriate section:

**For Static Scrapers** (BeautifulSoup + requests):
```python
# Add to static scrapers in run_static_scrapers function
executor.submit(scrape_newsite, product),
```

**For Dynamic Scrapers** (Playwright):
```python
# Add to gather_dynamic function
scrape_newsite_playwright(product, context),
```

### 3. Update Response Combination

Add your scraper to the `all_shops` list in `views.py`:
```python
all_shops = [
    {"name": "StarTech", **startech},
    {"name": "Ryans", **ryans},
    # ... existing shops ...
    {"name": "NewSite", **newsite},  # Add this line
]
```

### 4. Test Your Scraper

```python
# Test the scraper function directly
cd bdpricegear-backend
python manage.py shell
>>> from products.scraper import scrape_newsite
>>> result = scrape_newsite("mouse")
>>> print(result)
```

## 🚫 What NOT to Include

- **Secret keys** or API credentials (use `.env` file)
- **Large binary files** or browser downloads
- **`__pycache__/`** or `*.pyc` files (already in `.gitignore`)
- **`db.sqlite3`** database file (already in `.gitignore`)
- **`.venv/`** virtual environment (already in `.gitignore`)
- **Personal `.env`** files (already in `.gitignore`)
- **IDE configuration** files (VS Code, PyCharm settings)

## 📋 Pull Request Checklist

Before submitting a PR, ensure:

- [ ] Code follows our style guidelines
- [ ] Tests pass locally
- [ ] New features have tests
- [ ] Documentation is updated
- [ ] Commit messages follow conventions
- [ ] No merge conflicts with main branch
- [ ] PR description explains the changes

## 🔍 Code Review Process

1. **Automated checks** run on PR submission
2. **Maintainer review** for code quality and design
3. **Feedback** and requested changes
4. **Approval** and merge when ready

## 🎉 Recognition

Contributors will be:
- Listed in the project's contributors section
- Mentioned in release notes for significant contributions
- Given credit in documentation

## 🤔 Questions?

- Open an issue for general questions
- Join discussions in existing issues
- Contact maintainers directly for sensitive topics

## 📜 Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help newcomers learn
- Keep discussions on-topic

Thank you for contributing to BDPriceGear Backend! 🙏