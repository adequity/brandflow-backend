@echo off
echo BrandFlow PostgreSQL Password Reset
echo ====================================
echo.

echo This script will attempt to reset PostgreSQL password
echo You may need to run this as Administrator
echo.

echo Step 1: Stopping PostgreSQL service...
net stop postgresql-x64-17
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Could not stop PostgreSQL service
    echo Please run this script as Administrator
    pause
    exit /b 1
)

echo Step 2: Starting PostgreSQL in single-user mode...
echo (This will create a temporary configuration)

echo Step 3: You need to manually edit pg_hba.conf
echo Location: C:\Program Files\PostgreSQL\17\data\pg_hba.conf
echo.
echo Change this line:
echo   host    all             all             127.0.0.1/32            md5
echo To:
echo   host    all             all             127.0.0.1/32            trust
echo.
echo Then restart the service and run the database creation script

echo Step 4: Starting PostgreSQL service...
net start postgresql-x64-17
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS: PostgreSQL service restarted
    echo.
    echo Now you can try running:
    echo   python create_postgres_direct.py
) else (
    echo ERROR: Could not start PostgreSQL service
)

echo.
pause