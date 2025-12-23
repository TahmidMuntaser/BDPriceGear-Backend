# API Rate Limiting

## Overview
Rate limiting has been implemented to protect the API from abuse and ensure fair usage for all users.

## Rate Limits

### Default Limits

| User Type | Rate Limit | Description |
|-----------|------------|-------------|
| Anonymous | 100/hour | General API endpoints |
| Authenticated | 1000/hour | Registered users (future) |

### Endpoint-Specific Limits

| Endpoint | Rate Limit | Reason |
|----------|------------|--------|
| `/api/compare/` | 20/hour | Scraping-intensive (hits 7 websites per request) |
| `/api/update/` | 5/day | Admin operation, triggers full database update |
| `/api/products/` | 100/hour | Standard browsing |
| `/api/categories/` | 100/hour | Standard browsing |
| `/api/shops/` | 100/hour | Standard browsing |

## Rate Limit Headers

When you make a request, the response includes rate limit information in headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640000000
```

## When Rate Limit is Exceeded

If you exceed the rate limit, you'll receive:

**Status Code:** `429 Too Many Requests`

**Response:**
```json
{
  "detail": "Request was throttled. Expected available in 3600 seconds."
}
```

## Best Practices

1. **Cache responses** - Don't make repeated requests for the same data
2. **Use query parameters** - Filter results server-side instead of client-side
3. **Implement exponential backoff** - If you hit rate limits, wait before retrying
4. **Monitor headers** - Check `X-RateLimit-Remaining` to know your remaining quota

## Adjusting Limits (Development)

For local development, you can disable rate limiting by commenting out the throttle classes in `settings.py`:

```python
REST_FRAMEWORK = {
    # 'DEFAULT_THROTTLE_CLASSES': [  # Comment these out
    #     'rest_framework.throttling.AnonRateThrottle',
    #     'rest_framework.throttling.UserRateThrottle',
    # ],
}
```

## Implementation Details

Rate limiting is implemented using Django REST Framework's built-in throttling:

- **Storage:** In-memory cache (switches to Redis in production)
- **Scope-based:** Different endpoints can have different limits
- **IP-based:** Anonymous users are tracked by IP address
- **User-based:** Authenticated users tracked by user ID

## Production Considerations

For production with multiple server instances, configure Redis for rate limit storage:

```python
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}
```

This ensures rate limits work correctly across multiple server instances.
