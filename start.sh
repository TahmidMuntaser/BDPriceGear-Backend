#!/bin/bash
cd bdpricegear-backend
python manage.py collectstatic --noinput

# Skip migrations - database connection fails during build on Render
# Migrations will run automatically when the app starts if needed
echo "Skipping migrations during build phase"

# Increase worker timeout to 300 seconds to handle long database operations
gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --timeout 300 --workers 2