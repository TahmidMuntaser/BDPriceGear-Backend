from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    price_comparison,
    navbar_search,
    ProductViewSet, CategoryViewSet, ShopViewSet,
    ping, health_check, trigger_update, compare_product_prices,
    cleanup_old_data, trigger_catalog_update, cleanup_old_products,
    run_migrations, popular_products, reset_scraping_lock,
    add_to_wishlist, get_user_wishlist, remove_from_wishlist,
    subscribe_to_stock_notification, unsubscribe_from_stock_notification,
    chatbot_message
)
import os

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'shops', ShopViewSet, basename='shop')

# Base URLs (always available)
urlpatterns = [
    path('ping/', ping, name='ping'),
    path('search/', navbar_search, name='navbar-search'),
    path('price-comparison/', price_comparison, name='price-comparison'),
    path('products/<int:product_id>/compare/', compare_product_prices, name='compare-product-prices'),
    path('wishlist/', get_user_wishlist, name='wishlist-list'),
    path('wishlist/add/', add_to_wishlist, name='wishlist-add'),
    path('wishlist/remove/', remove_from_wishlist, name='wishlist-remove'),
    path('stock-notifications/subscribe/', subscribe_to_stock_notification, name='stock-notification-subscribe'),
    path('stock-notifications/unsubscribe/', unsubscribe_from_stock_notification, name='stock-notification-unsubscribe'),
    path('health/', health_check, name='health-check'),
    path('popular-products/', popular_products, name='popular-products'),
    path('chatbot/', chatbot_message, name='chatbot-message'),
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
        path('reset-scraping-lock/', reset_scraping_lock, name='reset-scraping-lock'),
    ]

