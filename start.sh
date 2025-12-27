#!/bin/bash
cd bdpricegear-backend
python manage.py collectstatic --noinput

# Try migration with timeout, continue if it fails
timeout 30 python manage.py migrate || echo "Migration skipped or timed out - will retry on app startup"

# Increase worker timeout to 300 seconds to handle long database operations
gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --timeout 300 --workers 2