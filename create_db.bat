@echo off
echo BrandFlow PostgreSQL Database Setup
echo =====================================
echo.

echo Trying common passwords...
echo.

echo Testing password: postgres
set PGPASSWORD=postgres
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d postgres -c "SELECT 'Connected with postgres password' as status;" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS: Connected with password 'postgres'
    goto :create_database
)

echo Testing password: admin
set PGPASSWORD=admin
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d postgres -c "SELECT 'Connected with admin password' as status;" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS: Connected with password 'admin'
    goto :create_database
)

echo Testing password: password
set PGPASSWORD=password
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d postgres -c "SELECT 'Connected with password password' as status;" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS: Connected with password 'password'
    goto :create_database
)

echo Testing password: 123456
set PGPASSWORD=123456
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d postgres -c "SELECT 'Connected with password 123456' as status;" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS: Connected with password '123456'
    goto :create_database
)

echo Testing no password (trust authentication)
set PGPASSWORD=
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d postgres -c "SELECT 'Connected with no password' as status;" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS: Connected with no password
    goto :create_database
)

echo.
echo ERROR: Could not connect to PostgreSQL with common passwords
echo.
echo Manual setup required:
echo 1. Open pgAdmin 4
echo 2. Connect to localhost:5432 with postgres user
echo 3. Run the SQL commands from brandflow_setup.sql
echo.
echo Or reset PostgreSQL password:
echo 1. Open services.msc
echo 2. Stop postgresql-x64-17 service
echo 3. Reinstall PostgreSQL with known password
goto :end

:create_database
echo.
echo Creating brandflow database and user...
echo.

echo Creating brandflow_user...
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d postgres -c "CREATE USER brandflow_user WITH PASSWORD 'brandflow_password_2024';" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS: brandflow_user created
) else (
    echo INFO: brandflow_user may already exist
)

echo Creating brandflow database...
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d postgres -c "CREATE DATABASE brandflow OWNER brandflow_user ENCODING 'UTF8';" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS: brandflow database created
) else (
    echo INFO: brandflow database may already exist
)

echo Granting privileges...
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE brandflow TO brandflow_user;" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS: privileges granted
) else (
    echo ERROR: failed to grant privileges
)

echo.
echo Testing brandflow database connection...
set PGPASSWORD=brandflow_password_2024
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U brandflow_user -d brandflow -c "SELECT 'BrandFlow database ready!' as status;" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS: brandflow database is ready!
    echo.
    echo Connection details:
    echo   Host: localhost
    echo   Port: 5432
    echo   Database: brandflow
    echo   User: brandflow_user
    echo   Password: brandflow_password_2024
    echo.
    echo Next steps:
    echo   1. python test_postgres_connection.py
    echo   2. python migrate_to_postgresql.py
    echo   3. Restart FastAPI server
) else (
    echo ERROR: Could not connect to brandflow database
)

:end
set PGPASSWORD=
echo.
pause