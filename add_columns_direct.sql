-- Railway PostgreSQL에서 campaigns 테이블에 날짜 컬럼 추가
-- 데이터베이스: postgresql://postgres:kAPUkGlWqoHwxIvtWaeukQuwcrZpSzuu@junction.proxy.rlwy.net:21652/railway

-- 1. 현재 campaigns 테이블 구조 확인
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'campaigns' 
ORDER BY ordinal_position;

-- 2. start_date 컬럼 추가 (이미 있으면 에러 무시)
ALTER TABLE campaigns 
ADD COLUMN IF NOT EXISTS start_date TIMESTAMP;

-- 3. end_date 컬럼 추가 (이미 있으면 에러 무시)
ALTER TABLE campaigns 
ADD COLUMN IF NOT EXISTS end_date TIMESTAMP;

-- 4. 기존 캠페인에 기본값 설정 (NULL인 경우만)
UPDATE campaigns 
SET start_date = COALESCE(start_date, CURRENT_TIMESTAMP),
    end_date = COALESCE(end_date, CURRENT_TIMESTAMP + INTERVAL '30 days')
WHERE start_date IS NULL OR end_date IS NULL;

-- 5. NOT NULL 제약조건 적용
ALTER TABLE campaigns ALTER COLUMN start_date SET NOT NULL;
ALTER TABLE campaigns ALTER COLUMN end_date SET NOT NULL;

-- 6. 최종 테이블 구조 확인
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'campaigns' 
ORDER BY ordinal_position;

-- 7. 샘플 데이터 확인
SELECT id, name, start_date, end_date 
FROM campaigns 
LIMIT 5;