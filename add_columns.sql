-- 구매요청 테이블에 누락된 컬럼 추가
-- Railway Shell에서 실행: psql $DATABASE_URL < add_columns.sql

-- priority 컬럼 추가 (이미 존재하면 에러 무시)
ALTER TABLE purchase_requests ADD COLUMN IF NOT EXISTS priority VARCHAR(50) DEFAULT '보통';

-- due_date 컬럼 추가
ALTER TABLE purchase_requests ADD COLUMN IF NOT EXISTS due_date DATE;

-- approver_comment 컬럼 추가
ALTER TABLE purchase_requests ADD COLUMN IF NOT EXISTS approver_comment TEXT;

-- reject_reason 컬럼 추가
ALTER TABLE purchase_requests ADD COLUMN IF NOT EXISTS reject_reason TEXT;

-- 결과 확인
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_name = 'purchase_requests'
AND column_name IN ('priority', 'due_date', 'approver_comment', 'reject_reason')
ORDER BY column_name;
