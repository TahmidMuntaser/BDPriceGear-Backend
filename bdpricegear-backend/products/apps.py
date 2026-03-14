from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'products'

    def ready(self):
        try:
            from django.core.cache import cache
            cache.delete('update_in_progress')
        except Exception:
            pass
