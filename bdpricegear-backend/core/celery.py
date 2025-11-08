"""
DEPRECATED: Celery and Redis have been removed in favor of APScheduler.
This file is kept for reference but is no longer used.

APScheduler handles hourly product updates without requiring Redis.
See: update_products_hourly.py
"""

import os
from celery import Celery

# This is no longer actively used
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
