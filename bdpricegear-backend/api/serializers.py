from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User


class SignupSerializer(serializers.ModelSerializer):
    """Serializer for user registration/signup"""
    
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text='Password must be at least 8 characters long'
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text='Confirm your password'
    )
    
    class Meta:
        model = User
        fields = ('email', 'password', 'confirm_password', 'first_name', 'last_name')
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
            'email': {
                'required': True,
                'help_text': 'Enter a valid email address'
            }
        }
    
    def validate_email(self, value):
        """Validate email is unique and properly formatted"""
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()
    
    def validate(self, attrs):
        """Validate password match and password strength"""
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')
        
        # Check if passwords match
        if password != confirm_password:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match.'
            })
        
        # Validate password strength using Django's validators
        try:
            validate_password(password)
        except ValidationError as e:
            raise serializers.ValidationError({
                'password': list(e.messages)
            })
        
        return attrs
    
    def create(self, validated_data):
        """Create a new user with encrypted password"""
        # Remove confirm_password as it's not part of the model
        validated_data.pop('confirm_password')
        
        # Create user using the custom manager (which handles password hashing)
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login/authentication"""
    
    email = serializers.EmailField(
        required=True,
        help_text='Your registered email address'
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text='Your password'
    )
    
    def validate(self, attrs):
        """Validate user credentials"""
        email = attrs.get('email', '').lower()
        password = attrs.get('password')
        
        if email and password:
            # Authenticate the user
            user = authenticate(
                request=self.context.get('request'),
                username=email,  # Our User model uses email as username
                password=password
            )
            
            if not user:
                raise serializers.ValidationError(
                    'Invalid email or password.',
                    code='authorization'
                )
            
            if not user.is_active:
                raise serializers.ValidationError(
                    'This account has been deactivated.',
                    code='authorization'
                )
            
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError(
                'Must include "email" and "password".',
                code='authorization'
            )


class UserSerializer(serializers.ModelSerializer):
    """Serializer for displaying user information"""
    
    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'date_joined', 'last_login')
        read_only_fields = ('id', 'date_joined', 'last_login')
