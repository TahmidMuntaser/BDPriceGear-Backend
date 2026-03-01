from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    price_comparison,
    ProductViewSet, CategoryViewSet, ShopViewSet,
    health_check, trigger_update, compare_product_prices,
    cleanup_old_data, trigger_catalog_update, cleanup_old_products,
    run_migrations, popular_products
)
import os

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'shops', ShopViewSet, basename='shop')

# Base URLs (always available)
urlpatterns = [
    path('price-comparison/', price_comparison, name='price-comparison'),
    path('products/<int:product_id>/compare/', compare_product_prices, name='compare-product-prices'),
    path('health/', health_check, name='health-check'),
    path('popular-products/', popular_products, name='popular-products'),
    path('', include(router.urls)),
]

# Scraping endpoints - only enabled on scraper service
ENABLE_SCRAPING = os.environ.get('ENABLE_SCRAPING_ENDPOINTS', 'True') == 'True'

if ENABLE_SCRAPING:
    urlpatterns += [
        path('update/', trigger_update, name='trigger-update'),
        path('catalog/update/', trigger_catalog_update, name='trigger-catalog-update'),
        path('cleanup/', cleanup_old_data, name='cleanup-old-data'),
        path('cleanup/products/', cleanup_old_products, name='cleanup-old-products'),
        path('migrate/', run_migrations, name='run-migrations'),
    ]

