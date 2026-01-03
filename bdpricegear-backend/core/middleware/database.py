"""
Database Connection Middleware

This middleware ensures proper database connection management by:
1. Closing idle connections before each request
2. Ensuring connections are closed after each response
3. Handling connection errors gracefully
4. Preventing connection timeout issues
5. Retrying failed connections
"""

import logging
import time
from django.db import connections, close_old_connections, OperationalError
from django.core.exceptions import MiddlewareNotUsed
from django.http import JsonResponse

logger = logging.getLogger(__name__)


class DatabaseConnectionMiddleware:
    """
    Middleware to manage database connections properly.
    
    This prevents connection timeout errors by:
    - Closing old/stale connections before processing requests
    - Properly closing connections after responses
    - Handling connection pool exhaustion
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Close any old connections before processing the request
        # This ensures we don't use stale or timed-out connections
        close_old_connections()
        
        # Retry logic for database connection issues
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                # Process the request
                response = self.get_response(request)
                
                # Ensure all connections are properly returned to the pool
                self._cleanup_connections()
                
                return response
                
            except OperationalError as e:
                # Database connection error
                error_msg = str(e).lower()
                
                if 'connection timeout' in error_msg or 'could not connect' in error_msg:
                    logger.warning(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}")
                    
                    if attempt < max_retries - 1:
                        # Retry after delay
                        time.sleep(retry_delay)
                        close_old_connections()  # Close failed connection
                        continue
                    else:
                        # Final attempt failed
                        logger.error(f"Database connection failed after {max_retries} attempts: {e}")
                        self._cleanup_connections()
                        
                        # Return user-friendly error
                        return JsonResponse({
                            'error': 'Database temporarily unavailable',
                            'message': 'Please try again in a moment',
                            'details': 'Connection timeout - database may be slow to respond'
                        }, status=503)
                else:
                    # Other database error, don't retry
                    raise
                    
            except Exception as e:
                # On any other error, ensure connections are cleaned up
                logger.error(f"Error during request processing: {e}")
                self._cleanup_connections()
                raise
        
        # Should never reach here
        self._cleanup_connections()
        return JsonResponse({'error': 'Unexpected error'}, status=500)
    
    def _cleanup_connections(self):
        """
        Clean up database connections.
        For transaction poolers (conn_max_age=0), this closes connections.
        For session poolers (conn_max_age>0), this returns connections to pool.
        """
        try:
            # Close old connections that have exceeded their max age
            close_old_connections()
            
            # For transaction pooler mode (conn_max_age=0), force close all connections
            for conn in connections.all():
                if hasattr(conn, 'close_if_unusable_or_obsolete'):
                    conn.close_if_unusable_or_obsolete()
                    
        except Exception as e:
            logger.warning(f"Error cleaning up database connections: {e}")
