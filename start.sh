#!/bin/bash
cd bdpricegear-backend
python manage.py collectstatic --noinput

# Skip migration during build - will run on first app request if needed
echo "Skipping migration during build to avoid connection timeout"

# Increase worker timeout to 300 seconds to handle long database operations
gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --timeout 300 --workers 2