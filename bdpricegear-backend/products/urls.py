from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    price_comparison, 
    ProductViewSet, CategoryViewSet, ShopViewSet,
    health_check
)

# Create router for ViewSets
router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'shops', ShopViewSet, basename='shop')

urlpatterns = [
    # Existing real-time price comparison endpoint
    path('price-comparison/', price_comparison, name='price-comparison'),
    
    # Health check endpoint (for UptimeRobot)
    path('health/', health_check, name='health-check'),
    
    # Product catalog API endpoints
    path('', include(router.urls)),
]

