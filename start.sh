#!/bin/bash
cd bdpricegear-backend
python manage.py collectstatic --noinput

# Skip migrations - database connection fails during build on Render
# Migrations will run automatically when the app starts if needed
echo "Skipping migrations during build phase"

# Use gunicorn configuration file for optimized settings
gunicorn core.wsgi:application --config gunicorn_config.py