from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class PriceComparisonThrottle(AnonRateThrottle):
    """
    Special throttle for price comparison endpoint
    Limits scraping-intensive operations
    """
    rate = '20/hour'
    scope = 'price_comparison'


class UpdateThrottle(AnonRateThrottle):
    """
    Special throttle for update endpoint
    Severely limits update operations
    """
    rate = '5/day'
    scope = 'update'
