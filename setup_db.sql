-- BrandFlow PostgreSQL Setup
-- 실행 방법: psql -U postgres -d postgres -f setup_db.sql

-- brandflow_user 생성
CREATE USER brandflow_user WITH PASSWORD 'brandflow_password_2024';

-- brandflow 데이터베이스 생성
CREATE DATABASE brandflow OWNER brandflow_user ENCODING 'UTF8';

-- 권한 부여
GRANT ALL PRIVILEGES ON DATABASE brandflow TO brandflow_user;

-- 연결 테스트
\c brandflow brandflow_user

-- 스키마 권한 설정
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO brandflow_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO brandflow_user;

-- 완료 메시지
SELECT 'BrandFlow PostgreSQL setup completed successfully!' AS status;