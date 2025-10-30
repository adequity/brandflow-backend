-- purchase_requests 테이블 스키마 확인
SELECT 
    column_name,
    data_type,
    character_maximum_length,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'purchase_requests'
ORDER BY ordinal_position;

-- 샘플 데이터 확인 (company 필드 중심으로)
SELECT 
    id,
    title,
    requester_id,
    company,
    created_at
FROM purchase_requests
ORDER BY created_at DESC
LIMIT 10;
