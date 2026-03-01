#!/bin/bash
# Setup script for BDPriceGear Backend after scraping fix

echo "========================================="
echo "BDPriceGear Backend - Setup Script"
echo "========================================="
echo ""

cd bdpricegear-backend

echo "Step 1: Creating cache table..."
python manage.py createcachetable

if [ $? -eq 0 ]; then
    echo " Cache table created successfully!"
else
    echo "Failed to create cache table"
    exit 1
fi

echo ""
echo "Step 2: Running migrations..."
python manage.py migrate

if [ $? -eq 0 ]; then
    echo "Migrations completed successfully!"
else
    echo "Failed to run migrations"
    exit 1
fi

echo ""
echo "Step 3: Collecting static files..."
python manage.py collectstatic --noinput

if [ $? -eq 0 ]; then
    echo "Static files collected!"
else
    echo "  Warning: Static files collection failed (may not be critical)"
fi

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Test the update endpoint:"
echo "   curl -X POST http://localhost:8000/api/update/"
echo ""
echo "2. Check status:"
echo "   curl http://localhost:8000/api/update/"
echo ""
echo "3. Start the server:"
echo "   gunicorn core.wsgi:application --config gunicorn_config.py"
echo ""
