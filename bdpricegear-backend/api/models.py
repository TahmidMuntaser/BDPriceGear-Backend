from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    """Custom user manager for email-based authentication"""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user with the given email and password"""
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # This hashes the password
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser with the given email and password"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model that uses email instead of username"""
    
    email = models.EmailField(
        unique=True,
        max_length=255,
        verbose_name='Email Address',
        help_text='Required. Enter a valid email address.'
    )
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)
    
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Email is already required by USERNAME_FIELD
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        db_table = 'users'
        ordering = ['-date_joined']
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between"""
        full_name = f'{self.first_name} {self.last_name}'.strip()
        return full_name or self.email
    
    def get_short_name(self):
        """Return the short name for the user"""
        return self.first_name or self.email
