# BDPriceGear Backend Documentation

Welcome to the BDPriceGear Backend documentation! This API provides real-time price comparison across multiple Bangladeshi e-commerce platforms.

## 🚀 Quick Start

- [Installation Guide](setup/installation.md)
- [API Reference](api/endpoints.md)
- [Deployment Guide](deployment/production.md)

## 📚 Documentation Sections

### 🛠️ Setup & Development
- [Installation](setup/installation.md) - How to set up the development environment
- [Requirements](setup/requirements.md) - System and Python requirements
- [Development Guide](setup/development.md) - Development workflow and tools

### 🔌 API Documentation
- [Endpoints](api/endpoints.md) - Complete API reference
- [Authentication](api/authentication.md) - API security and access
- [Examples](api/examples.md) - Request/response examples
- [Error Handling](api/errors.md) - Error codes and troubleshooting

### 🚀 Deployment
- [Production Setup](deployment/production.md) - Production deployment guide
- [Docker Setup](deployment/docker.md) - Containerization guide
- [Environment Variables](deployment/environment.md) - Configuration options

### 🤝 Contributing
- [Contribution Guidelines](contributing/guidelines.md) - How to contribute
- [Code Style](contributing/code-style.md) - Coding standards
- [Testing](contributing/testing.md) - Testing guidelines

## 🏪 Supported E-commerce Sites

The API scrapes prices from these Bangladeshi e-commerce platforms:

1. **StarTech** - Static scraper
2. **Ryans** - Dynamic scraper (Playwright)
3. **Binary Logic** - Dynamic scraper (Playwright)  
4. **Skyland** - Static scraper
5. **PC House** - Static scraper
6. **UltraTech** - Static scraper
7. **PotakaIT** - Static scraper

## 🔧 Technology Stack

- **Framework**: Django 5.2.5 + Django REST Framework
- **Web Scraping**: BeautifulSoup4, Playwright, Requests
- **Concurrency**: AsyncIO, ThreadPoolExecutor
- **Documentation**: drf-yasg (Swagger/OpenAPI)
- **Database**: SQLite (development)

## 📞 Support

For issues and questions:
- Create an issue on GitHub
- Check the [API Examples](api/examples.md)
- Review [Error Handling](api/errors.md) guide

---

**Made with ❤️ for Bangladeshi e-commerce price comparison**