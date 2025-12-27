#!/bin/bash
cd bdpricegear-backend
python manage.py collectstatic --noinput

# Run migrations (should work now with transaction pooler)
python manage.py migrate --noinput || echo "Migration failed, continuing..."

# Increase worker timeout to 300 seconds to handle long database operations
gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --timeout 300 --workers 2