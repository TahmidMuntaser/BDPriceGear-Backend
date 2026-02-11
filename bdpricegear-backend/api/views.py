from django.shortcuts import render
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import login
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import logging

from .serializers import SignupSerializer, LoginSerializer, UserSerializer
from .models import User

logger = logging.getLogger(__name__)


class AuthRateThrottle(AnonRateThrottle):
    """Custom throttle for authentication endpoints - 5 requests per minute"""
    rate = '5/min'


def get_tokens_for_user(user):
    """Generate JWT tokens for a user"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


@swagger_auto_schema(
    method='post',
    request_body=SignupSerializer,
    responses={
        201: openapi.Response(
            description="User created successfully",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'message': openapi.Schema(type=openapi.TYPE_STRING),
                    'user': openapi.Schema(type=openapi.TYPE_OBJECT),
                    'tokens': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'access': openapi.Schema(type=openapi.TYPE_STRING),
                            'refresh': openapi.Schema(type=openapi.TYPE_STRING),
                        }
                    ),
                }
            )
        ),
        400: "Bad Request - Validation errors"
    },
    operation_description="Register a new user account with email and password",
    operation_id="signup",
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([AuthRateThrottle])
def signup_view(request):
    """
    User registration endpoint
    
    Security features:
    - Rate limiting (5 requests/min)
    - Password strength validation
    - Email uniqueness check
    - Password hashing with Django's default (PBKDF2)
    - CSRF protection
    """
    serializer = SignupSerializer(data=request.data)
    
    if serializer.is_valid():
        try:
            # Create the user
            user = serializer.save()
            
            # Generate JWT tokens
            tokens = get_tokens_for_user(user)
            
            # Log successful signup
            logger.info(f"New user registered: {user.email}")
            
            # Return user data and tokens
            return Response({
                'message': 'User created successfully',
                'user': UserSerializer(user).data,
                'tokens': tokens
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error during signup: {str(e)}")
            return Response({
                'error': 'An error occurred during registration. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    request_body=LoginSerializer,
    responses={
        200: openapi.Response(
            description="Login successful",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'message': openapi.Schema(type=openapi.TYPE_STRING),
                    'user': openapi.Schema(type=openapi.TYPE_OBJECT),
                    'tokens': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'access': openapi.Schema(type=openapi.TYPE_STRING),
                            'refresh': openapi.Schema(type=openapi.TYPE_STRING),
                        }
                    ),
                }
            )
        ),
        400: "Bad Request - Invalid credentials",
        401: "Unauthorized - Invalid email or password"
    },
    operation_description="Login with email and password to receive JWT tokens",
    operation_id="login",
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([AuthRateThrottle])
def login_view(request):
    """
    User login endpoint
    
    Security features:
    - Rate limiting (5 requests/min)
    - Account lockout for inactive users
    - Secure password verification
    - JWT token generation
    - Last login timestamp update
    """
    serializer = LoginSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        try:
            user = serializer.validated_data['user']
            
            # Update last login timestamp
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
            
            # Generate JWT tokens
            tokens = get_tokens_for_user(user)
            
            # Log successful login
            logger.info(f"User logged in: {user.email}")
            
            return Response({
                'message': 'Login successful',
                'user': UserSerializer(user).data,
                'tokens': tokens
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error during login: {str(e)}")
            return Response({
                'error': 'An error occurred during login. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['refresh'],
        properties={
            'refresh': openapi.Schema(type=openapi.TYPE_STRING, description='Refresh token'),
        }
    ),
    responses={
        200: openapi.Response(
            description="Token refreshed successfully",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'access': openapi.Schema(type=openapi.TYPE_STRING),
                }
            )
        ),
        400: "Bad Request - Invalid token"
    },
    operation_description="Refresh access token using refresh token",
    operation_id="refresh_token",
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def refresh_token_view(request):
    """
    Refresh JWT access token
    
    Use this endpoint when your access token expires.
    Provide the refresh token to get a new access token.
    """
    refresh_token = request.data.get('refresh')
    
    if not refresh_token:
        return Response({
            'error': 'Refresh token is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        refresh = RefreshToken(refresh_token)
        access_token = str(refresh.access_token)
        
        return Response({
            'access': access_token
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        return Response({
            'error': 'Invalid or expired refresh token'
        }, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    responses={
        200: "Logout successful",
        400: "Bad Request - Invalid token"
    },
    operation_description="Logout and blacklist the refresh token",
    operation_id="logout",
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    """
    User logout endpoint
    
    Blacklists the refresh token to prevent reuse.
    Requires authentication.
    """
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        
        logger.info(f"User logged out: {request.user.email}")
        
        return Response({
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
        return Response({
            'error': 'An error occurred during logout'
        }, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    responses={
        200: UserSerializer,
        401: "Unauthorized"
    },
    operation_description="Get current authenticated user's profile",
    operation_id="user_profile",
    tags=['Authentication']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_profile_view(request):
    """
    Get current user's profile
    
    Requires authentication via JWT token.
    Include token in header: Authorization: Bearer <access_token>
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data, status=status.HTTP_200_OK)
