-- BrandFlow PostgreSQL Database Setup Script
-- 이 스크립트는 brandflow 데이터베이스와 사용자를 생성합니다.

-- brandflow 사용자 생성 (이미 존재하면 무시)
DO
$$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'brandflow_user') THEN
      CREATE ROLE brandflow_user LOGIN PASSWORD 'brandflow_password_2024';
   END IF;
END
$$;

-- brandflow 데이터베이스 생성 (이미 존재하면 무시)
SELECT 'CREATE DATABASE brandflow OWNER brandflow_user ENCODING ''UTF8'' LC_COLLATE=''C'' LC_CTYPE=''C'''
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'brandflow')\gexec

-- brandflow_user에게 데이터베이스 권한 부여
GRANT ALL PRIVILEGES ON DATABASE brandflow TO brandflow_user;

-- 연결 확인
\c brandflow brandflow_user

-- 기본 권한 설정
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO brandflow_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO brandflow_user;