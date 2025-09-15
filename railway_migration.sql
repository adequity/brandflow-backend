-- Railway에서 직접 실행할 SQL 마이그레이션
-- campaigns 테이블에 start_date, end_date 컬럼 추가

-- 1. 현재 campaigns 테이블 구조 확인
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'campaigns' 
ORDER BY ordinal_position;

-- 2. start_date 컬럼 추가 (nullable로 시작)
ALTER TABLE campaigns 
ADD COLUMN IF NOT EXISTS start_date TIMESTAMP;

-- 3. end_date 컬럼 추가 (nullable로 시작)
ALTER TABLE campaigns 
ADD COLUMN IF NOT EXISTS end_date TIMESTAMP;

-- 4. 기존 데이터에 기본값 설정 (현재 타임스탬프)
UPDATE campaigns 
SET start_date = CURRENT_TIMESTAMP, end_date = CURRENT_TIMESTAMP 
WHERE start_date IS NULL OR end_date IS NULL;

-- 5. 컬럼을 NOT NULL로 변경
ALTER TABLE campaigns 
ALTER COLUMN start_date SET NOT NULL;

ALTER TABLE campaigns 
ALTER COLUMN end_date SET NOT NULL;

-- 6. 최종 테이블 구조 확인
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'campaigns' 
ORDER BY ordinal_position;