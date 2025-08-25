#!/usr/bin/env python3
"""
Simple PostgreSQL database setup using psycopg2
"""

import psycopg2
import sys


def create_database():
    """Create PostgreSQL database and user"""
    print("PostgreSQL database setup starting...")
    
    # Try different connection methods
    connection_attempts = [
        # No password (trust authentication)
        {
            'host': 'localhost',
            'port': '5432', 
            'database': 'postgres',
            'user': 'postgres',
            'password': ''
        },
        # Common passwords
        {
            'host': 'localhost',
            'port': '5432',
            'database': 'postgres', 
            'user': 'postgres',
            'password': 'postgres'
        },
        {
            'host': 'localhost',
            'port': '5432',
            'database': 'postgres',
            'user': 'postgres', 
            'password': 'admin'
        },
        {
            'host': 'localhost',
            'port': '5432',
            'database': 'postgres',
            'user': 'postgres',
            'password': 'password'
        }
    ]
    
    conn = None
    for i, params in enumerate(connection_attempts, 1):
        try:
            print(f"Attempt {i}: Connecting to PostgreSQL...")
            conn = psycopg2.connect(**params)
            conn.autocommit = True
            print("Connection successful!")
            break
        except Exception as e:
            print(f"Failed: {e}")
            continue
    
    if not conn:
        print("All automatic connection attempts failed.")
        # Try manual password input
        try:
            password = input("Enter PostgreSQL postgres user password: ")
            conn = psycopg2.connect(
                host='localhost',
                port='5432',
                database='postgres',
                user='postgres',
                password=password
            )
            conn.autocommit = True
            print("Manual connection successful!")
        except Exception as e:
            print(f"Manual connection failed: {e}")
            return False
    
    try:
        cursor = conn.cursor()
        
        # Create user if not exists
        try:
            cursor.execute("""
                CREATE USER brandflow_user WITH PASSWORD 'brandflow_password_2024'
            """)
            print("brandflow_user created")
        except psycopg2.errors.DuplicateObject:
            print("brandflow_user already exists")
        except Exception as e:
            print(f"User creation error: {e}")
        
        # Create database if not exists
        try:
            cursor.execute("""
                CREATE DATABASE brandflow OWNER brandflow_user 
                ENCODING 'UTF8' LC_COLLATE='C' LC_CTYPE='C'
            """)
            print("brandflow database created")
        except psycopg2.errors.DuplicateDatabase:
            print("brandflow database already exists")
        except Exception as e:
            print(f"Database creation error: {e}")
        
        # Grant privileges
        try:
            cursor.execute("GRANT ALL PRIVILEGES ON DATABASE brandflow TO brandflow_user")
            print("Privileges granted")
        except Exception as e:
            print(f"Grant privileges error: {e}")
        
        cursor.close()
        conn.close()
        
        # Test brandflow database connection
        print("\nTesting brandflow database connection...")
        try:
            test_conn = psycopg2.connect(
                host='localhost',
                port='5432',
                database='brandflow',
                user='brandflow_user',
                password='brandflow_password_2024'
            )
            
            test_cursor = test_conn.cursor()
            test_cursor.execute("SELECT version()")
            version = test_cursor.fetchone()[0]
            print(f"Connection successful! PostgreSQL version: {version.split()[1]}")
            
            # Test table operations
            test_cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100)
                )
            """)
            test_cursor.execute("INSERT INTO test_table (name) VALUES ('test')")
            test_cursor.execute("SELECT COUNT(*) FROM test_table")
            count = test_cursor.fetchone()[0]
            test_cursor.execute("DROP TABLE test_table")
            test_conn.commit()
            
            print(f"Table operations test successful (records: {count})")
            
            test_cursor.close()
            test_conn.close()
            
            print("\nPostgreSQL database setup completed successfully!")
            print("\nConnection info:")
            print("  Host: localhost")
            print("  Port: 5432")
            print("  Database: brandflow")
            print("  User: brandflow_user")
            print("  Password: brandflow_password_2024")
            print("\nNext steps:")
            print("1. python migrate_to_postgresql.py")
            print("2. copy .env.postgresql .env")
            print("3. Restart FastAPI server")
            
            return True
            
        except Exception as e:
            print(f"brandflow database connection test failed: {e}")
            return False
        
    except Exception as e:
        print(f"Database setup failed: {e}")
        if conn:
            conn.close()
        return False


if __name__ == "__main__":
    success = create_database()
    sys.exit(0 if success else 1)