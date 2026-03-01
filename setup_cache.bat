@echo off
REM Setup script for BDPriceGear Backend on Windows

echo =========================================
echo BDPriceGear Backend - Setup Script
echo =========================================
echo.

cd bdpricegear-backend

echo Step 1: Creating cache table...
python manage.py createcachetable

if %ERRORLEVEL% EQU 0 (
    echo ✓ Cache table created successfully!
) else (
    echo ✗ Failed to create cache table
    exit /b 1
)

echo.
echo Step 2: Running migrations...
python manage.py migrate

if %ERRORLEVEL% EQU 0 (
    echo ✓ Migrations completed successfully!
) else (
    echo ✗ Failed to run migrations
    exit /b 1
)

echo.
echo Step 3: Collecting static files...
python manage.py collectstatic --noinput

if %ERRORLEVEL% EQU 0 (
    echo ✓ Static files collected!
) else (
    echo ! Warning: Static files collection failed
)

echo.
echo =========================================
echo Setup Complete!
echo =========================================
echo.
echo Next steps:
echo 1. Test the update endpoint:
echo    curl -X POST http://localhost:8000/api/update/
echo.
echo 2. Check status:
echo    curl http://localhost:8000/api/update/
echo.
echo 3. Start the server:
echo    python manage.py runserver
echo.
pause
