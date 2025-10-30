-- ============================================================================
-- purchase_requests 테이블 NULL 값을 기본값으로 업데이트
-- ============================================================================
-- 목적: NULL 값을 의미 있는 기본값으로 변경하여 필터링/정렬 문제 해결
-- 작성일: 2025-10-30
-- ============================================================================

-- 1️⃣ 현재 NULL 값 통계 확인
-- ============================================================================
SELECT
    '필드별 NULL 개수' as info,
    COUNT(CASE WHEN description IS NULL THEN 1 END) as description_null,
    COUNT(CASE WHEN vendor IS NULL THEN 1 END) as vendor_null,
    COUNT(CASE WHEN resource_type IS NULL THEN 1 END) as resource_type_null,
    COUNT(CASE WHEN receipt_file_url IS NULL THEN 1 END) as receipt_file_url_null,
    COUNT(CASE WHEN attachment_urls IS NULL THEN 1 END) as attachment_urls_null,
    COUNT(CASE WHEN approver_comment IS NULL THEN 1 END) as approver_comment_null,
    COUNT(CASE WHEN reject_reason IS NULL THEN 1 END) as reject_reason_null,
    COUNT(*) as total_records
FROM purchase_requests;

-- 2️⃣ NULL 값 업데이트 실행
-- ============================================================================

-- description: NULL → '' (빈 문자열)
UPDATE purchase_requests
SET description = '', updated_at = NOW()
WHERE description IS NULL;

-- vendor: NULL → '' (빈 문자열)
UPDATE purchase_requests
SET vendor = '', updated_at = NOW()
WHERE vendor IS NULL;

-- resource_type: NULL → '기타'
UPDATE purchase_requests
SET resource_type = '기타', updated_at = NOW()
WHERE resource_type IS NULL;

-- receipt_file_url: NULL → '' (빈 문자열)
UPDATE purchase_requests
SET receipt_file_url = '', updated_at = NOW()
WHERE receipt_file_url IS NULL;

-- attachment_urls: NULL → '[]' (빈 JSON 배열)
UPDATE purchase_requests
SET attachment_urls = '[]', updated_at = NOW()
WHERE attachment_urls IS NULL;

-- approver_comment: NULL → '' (빈 문자열)
UPDATE purchase_requests
SET approver_comment = '', updated_at = NOW()
WHERE approver_comment IS NULL;

-- reject_reason: NULL → '' (빈 문자열)
UPDATE purchase_requests
SET reject_reason = '', updated_at = NOW()
WHERE reject_reason IS NULL;

-- due_date는 NULL 유지 (실제 미설정 상태를 의미하므로)
-- campaign_id는 NULL 유지 (실제 캠페인이 없을 수 있으므로)

-- 3️⃣ 업데이트 결과 확인
-- ============================================================================
SELECT
    '업데이트 후 NULL 개수' as info,
    COUNT(CASE WHEN description IS NULL THEN 1 END) as description_null,
    COUNT(CASE WHEN vendor IS NULL THEN 1 END) as vendor_null,
    COUNT(CASE WHEN resource_type IS NULL THEN 1 END) as resource_type_null,
    COUNT(CASE WHEN receipt_file_url IS NULL THEN 1 END) as receipt_file_url_null,
    COUNT(CASE WHEN attachment_urls IS NULL THEN 1 END) as attachment_urls_null,
    COUNT(CASE WHEN approver_comment IS NULL THEN 1 END) as approver_comment_null,
    COUNT(CASE WHEN reject_reason IS NULL THEN 1 END) as reject_reason_null,
    COUNT(*) as total_records
FROM purchase_requests;

-- 4️⃣ 샘플 데이터 확인
-- ============================================================================
SELECT
    id,
    title,
    COALESCE(description, '(NULL)') as description,
    COALESCE(vendor, '(NULL)') as vendor,
    COALESCE(resource_type, '(NULL)') as resource_type,
    COALESCE(receipt_file_url, '(NULL)') as receipt_file_url,
    COALESCE(attachment_urls, '(NULL)') as attachment_urls,
    status,
    created_at
FROM purchase_requests
ORDER BY created_at DESC
LIMIT 10;

-- 5️⃣ resource_type 분포 확인
-- ============================================================================
SELECT
    COALESCE(resource_type, '(미분류)') as resource_type,
    COUNT(*) as count,
    SUM(amount) as total_amount,
    AVG(amount) as avg_amount
FROM purchase_requests
GROUP BY resource_type
ORDER BY count DESC;

-- ============================================================================
-- 📝 실행 가이드
-- ============================================================================
-- 1. 먼저 1️⃣을 실행하여 현재 NULL 값 개수 확인
-- 2. 2️⃣의 UPDATE 쿼리들을 순서대로 실행
-- 3. 3️⃣으로 업데이트 결과 확인 (NULL이 0이 되어야 함)
-- 4. 4️⃣, 5️⃣로 실제 데이터 확인
--
-- ⚠️ 주의:
-- - due_date와 campaign_id는 NULL을 유지합니다 (의미 있는 NULL)
-- - 실행 후 되돌릴 수 없으므로 신중하게 실행하세요
-- ============================================================================
