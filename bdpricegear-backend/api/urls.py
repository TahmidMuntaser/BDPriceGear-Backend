from django.urls import path
from .views import (
    signup_view,
    login_view,
    logout_view,
    refresh_token_view,
    user_profile_view
)

urlpatterns = [
    path('auth/signup/', signup_view, name='signup'),
    path('auth/login/', login_view, name='login'),
    path('auth/logout/', logout_view, name='logout'),
    path('auth/refresh/', refresh_token_view, name='token_refresh'),
    path('auth/profile/', user_profile_view, name='user_profile'),
]
