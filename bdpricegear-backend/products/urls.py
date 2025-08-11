from django.urls import path
from .views import price_comparison

urlpatterns = [
    path('price-comparison/', price_comparison, name='price-comparison'),
]
