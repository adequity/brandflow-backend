import os

print('DATABASE_URL exists:', 'DATABASE_URL' in os.environ)
if 'DATABASE_URL' in os.environ:
    db_url = os.environ['DATABASE_URL']
    print('DATABASE_URL format:', db_url[:50] + '...' if len(db_url) > 50 else db_url)