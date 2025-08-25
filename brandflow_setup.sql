-- BrandFlow PostgreSQL Setup
-- 이 파일을 PostgreSQL에서 직접 실행하세요

-- 1. brandflow_user 생성
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_catalog.pg_roles 
        WHERE rolname = 'brandflow_user'
    ) THEN
        CREATE USER brandflow_user WITH PASSWORD 'brandflow_password_2024';
        RAISE NOTICE 'brandflow_user created';
    ELSE
        RAISE NOTICE 'brandflow_user already exists';
    END IF;
END $$;

-- 2. brandflow 데이터베이스 생성
SELECT 'CREATE DATABASE brandflow OWNER brandflow_user ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'brandflow')\gexec

-- 3. 권한 부여
GRANT ALL PRIVILEGES ON DATABASE brandflow TO brandflow_user;

-- 4. 연결 테스트용 (brandflow 데이터베이스에서 실행)
\c brandflow brandflow_user

-- 5. 성공 메시지
SELECT 'BrandFlow PostgreSQL setup completed successfully!' as status;

-- 연결 정보 확인
SELECT current_database() as database, current_user as user;
