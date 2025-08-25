@echo off
echo Setting up BrandFlow PostgreSQL database...
echo.

set PGPASSWORD=postgres
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d postgres -c "CREATE USER brandflow_user WITH PASSWORD 'brandflow_password_2024';" 2>nul
echo Creating brandflow_user...

set PGPASSWORD=postgres
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d postgres -c "CREATE DATABASE brandflow OWNER brandflow_user ENCODING 'UTF8';" 2>nul
echo Creating brandflow database...

set PGPASSWORD=postgres
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE brandflow TO brandflow_user;" 2>nul
echo Granting privileges...

echo.
echo Testing connection to brandflow database...
set PGPASSWORD=brandflow_password_2024
"C:\Program Files\PostgreSQL\17\bin\psql.exe" -U brandflow_user -d brandflow -c "SELECT 'Connection successful!' as status;" 2>nul

echo.
echo PostgreSQL setup completed!
echo Connection details:
echo   Host: localhost
echo   Port: 5432
echo   Database: brandflow
echo   User: brandflow_user
echo   Password: brandflow_password_2024
echo.
echo Next steps:
echo   1. python migrate_to_postgresql.py
echo   2. copy .env.postgresql .env
echo   3. Restart FastAPI server

set PGPASSWORD=