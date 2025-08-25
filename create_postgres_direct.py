#!/usr/bin/env python3
"""
Direct PostgreSQL database creation with multiple password attempts
"""

import subprocess
import sys
import os

def run_psql_command(password, command, user="postgres", database="postgres"):
    """Run a psql command with given password"""
    env = os.environ.copy()
    env['PGPASSWORD'] = password
    
    cmd = [
        r"C:\Program Files\PostgreSQL\17\bin\psql.exe",
        "-U", user,
        "-d", database,
        "-c", command
    ]
    
    try:
        result = subprocess.run(
            cmd, 
            env=env, 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def test_connection():
    """Test PostgreSQL connection with common passwords"""
    passwords = ['postgres', 'admin', 'password', '123456', '']
    
    print("=" * 50)
    print("BrandFlow PostgreSQL Connection Test")
    print("=" * 50)
    
    for password in passwords:
        print(f"\nTesting password: {'(empty)' if password == '' else password}")
        
        success, stdout, stderr = run_psql_command(
            password, 
            "SELECT 'Connection successful!' as status;"
        )
        
        if success:
            print(f"SUCCESS! Connected with password: {'(empty)' if password == '' else password}")
            return password
        else:
            print(f"Failed: {stderr}")
    
    print("\nAll password attempts failed.")
    print("\nManual steps required:")
    print("1. Open pgAdmin 4")
    print("2. Connect to PostgreSQL server")
    print("3. Run the SQL from brandflow_setup.sql")
    return None

def create_database(password):
    """Create brandflow database and user"""
    print(f"\nCreating database with password: {'(empty)' if password == '' else password}")
    print("-" * 30)
    
    commands = [
        ("Creating brandflow_user", "CREATE USER brandflow_user WITH PASSWORD 'brandflow_password_2024';"),
        ("Creating brandflow database", "CREATE DATABASE brandflow OWNER brandflow_user ENCODING 'UTF8';"),
        ("Granting privileges", "GRANT ALL PRIVILEGES ON DATABASE brandflow TO brandflow_user;")
    ]
    
    for description, command in commands:
        print(f"{description}...")
        success, stdout, stderr = run_psql_command(password, command)
        
        if success:
            print(f"  SUCCESS: {description}")
        else:
            if "already exists" in stderr.lower():
                print(f"  INFO: Already exists")
            else:
                print(f"  ERROR: {stderr}")
    
    # Test brandflow database connection
    print("\nTesting brandflow database connection...")
    success, stdout, stderr = run_psql_command(
        'brandflow_password_2024',
        "SELECT 'BrandFlow database ready!' as status;",
        user="brandflow_user",
        database="brandflow"
    )
    
    if success:
        print("SUCCESS: brandflow database is ready!")
        print("\nConnection details:")
        print("  Host: localhost")
        print("  Port: 5432") 
        print("  Database: brandflow")
        print("  User: brandflow_user")
        print("  Password: brandflow_password_2024")
        print("\nNext steps:")
        print("  1. python test_postgres_connection.py")
        print("  2. python migrate_to_postgresql.py")
        print("  3. Restart FastAPI server")
        return True
    else:
        print(f"ERROR: Could not connect to brandflow database: {stderr}")
        return False

def main():
    # Test connection first
    working_password = test_connection()
    
    if working_password is not None:
        # Create database
        success = create_database(working_password)
        return 0 if success else 1
    else:
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)