-- ============================================================================
-- purchase_requests 테이블의 company 필드 자동 업데이트 스크립트
-- ============================================================================
-- 목적: requester_id를 기반으로 users 테이블의 company 값을 자동으로 매칭
-- 작성일: 2025-10-30
-- ============================================================================

-- 1. 현재 상태 확인 (실행 전)
-- ============================================================================
SELECT
    '실행 전 상태' as status,
    COUNT(*) as total_purchase_requests,
    COUNT(CASE WHEN company IS NULL OR company = '' THEN 1 END) as null_company_count,
    COUNT(CASE WHEN company IS NOT NULL AND company != '' THEN 1 END) as has_company_count
FROM purchase_requests;

-- 2. company가 NULL이거나 빈 값인 레코드 상세 확인
-- ============================================================================
SELECT
    pr.id,
    pr.title,
    pr.requester_id,
    pr.company as current_company,
    u.name as requester_name,
    u.company as user_company,
    pr.created_at
FROM purchase_requests pr
LEFT JOIN users u ON pr.requester_id = u.id
WHERE pr.company IS NULL OR pr.company = '' OR pr.company = 'default_company'
ORDER BY pr.created_at DESC;

-- 3. 업데이트 실행 (company가 NULL이거나 빈 값인 경우)
-- ============================================================================
UPDATE purchase_requests pr
SET
    company = u.company,
    updated_at = NOW()
FROM users u
WHERE pr.requester_id = u.id
  AND (pr.company IS NULL OR pr.company = '' OR pr.company = 'default_company')
  AND u.company IS NOT NULL;

-- 4. 결과 확인 (실행 후)
-- ============================================================================
SELECT
    '실행 후 상태' as status,
    COUNT(*) as total_purchase_requests,
    COUNT(CASE WHEN company IS NULL OR company = '' THEN 1 END) as null_company_count,
    COUNT(CASE WHEN company IS NOT NULL AND company != '' THEN 1 END) as has_company_count
FROM purchase_requests;

-- 5. 업데이트된 레코드 확인
-- ============================================================================
SELECT
    pr.id,
    pr.title,
    pr.requester_id,
    pr.company,
    u.name as requester_name,
    u.company as user_company,
    pr.updated_at
FROM purchase_requests pr
LEFT JOIN users u ON pr.requester_id = u.id
WHERE pr.updated_at >= NOW() - INTERVAL '1 minute'
ORDER BY pr.updated_at DESC;

-- 6. company별 구매요청 통계
-- ============================================================================
SELECT
    COALESCE(pr.company, '(NULL)') as company,
    COUNT(*) as purchase_request_count,
    COUNT(DISTINCT pr.requester_id) as unique_requesters,
    SUM(pr.amount) as total_amount,
    AVG(pr.amount) as avg_amount
FROM purchase_requests pr
GROUP BY pr.company
ORDER BY purchase_request_count DESC;

-- 7. 여전히 company가 NULL인 레코드 확인 (requester가 없거나 user.company가 NULL인 경우)
-- ============================================================================
SELECT
    pr.id,
    pr.title,
    pr.requester_id,
    pr.company,
    u.name as requester_name,
    u.company as user_company,
    CASE
        WHEN u.id IS NULL THEN '요청자 삭제됨'
        WHEN u.company IS NULL THEN '사용자 company NULL'
        ELSE '알 수 없음'
    END as issue
FROM purchase_requests pr
LEFT JOIN users u ON pr.requester_id = u.id
WHERE pr.company IS NULL OR pr.company = ''
ORDER BY pr.created_at DESC;

-- ============================================================================
-- 실행 방법 (pgAdmin):
-- ============================================================================
-- 1. 위의 쿼리를 순서대로 실행하거나
-- 2. 전체 선택 후 F5 (Execute)
-- 3. 각 단계의 결과를 확인하면서 진행
--
-- 주의사항:
-- - UPDATE 쿼리는 실제 데이터를 변경하므로 신중하게 실행
-- - 1, 2번 쿼리로 먼저 상태 확인 후 3번 UPDATE 실행 권장
-- - Railway 프로덕션 DB에서 실행 시 백업 권장
-- ============================================================================
