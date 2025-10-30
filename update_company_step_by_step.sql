-- ============================================================================
-- 단계별 안전 업데이트 스크립트 (pgAdmin용)
-- ============================================================================

-- ===== STEP 1: 현재 상태 확인 =====
-- 이 쿼리를 먼저 실행하여 업데이트가 필요한 레코드 수를 확인하세요
-- ============================================================================
SELECT
    '업데이트 필요한 레코드' as info,
    COUNT(*) as count
FROM purchase_requests
WHERE company IS NULL OR company = '' OR company = 'default_company';

-- ===== STEP 2: 업데이트 대상 상세 확인 =====
-- 어떤 데이터가 업데이트될지 미리 확인하세요
-- ============================================================================
SELECT
    pr.id,
    pr.title,
    pr.requester_id,
    pr.company as 현재_company,
    u.company as 업데이트될_company,
    u.name as 요청자명,
    u.role as 요청자역할
FROM purchase_requests pr
INNER JOIN users u ON pr.requester_id = u.id
WHERE (pr.company IS NULL OR pr.company = '' OR pr.company = 'default_company')
  AND u.company IS NOT NULL
ORDER BY pr.id;

-- ===== STEP 3: 업데이트 실행 =====
-- 위의 결과를 확인한 후 이 쿼리를 실행하세요
-- ============================================================================
UPDATE purchase_requests pr
SET
    company = u.company,
    updated_at = NOW()
FROM users u
WHERE pr.requester_id = u.id
  AND (pr.company IS NULL OR pr.company = '' OR pr.company = 'default_company')
  AND u.company IS NOT NULL;

-- ===== STEP 4: 업데이트 결과 확인 =====
-- 업데이트가 성공적으로 완료되었는지 확인하세요
-- ============================================================================
SELECT
    '업데이트 완료' as status,
    COUNT(*) as updated_count
FROM purchase_requests
WHERE updated_at >= NOW() - INTERVAL '5 minutes'
  AND company IS NOT NULL
  AND company != ''
  AND company != 'default_company';

-- ===== STEP 5: 여전히 문제가 있는 레코드 확인 =====
-- company가 여전히 NULL인 레코드가 있다면 확인하세요
-- ============================================================================
SELECT
    pr.id,
    pr.title,
    pr.requester_id,
    pr.company,
    CASE
        WHEN u.id IS NULL THEN '❌ 요청자가 삭제됨'
        WHEN u.company IS NULL THEN '⚠️ 사용자의 company가 NULL'
        WHEN u.company = '' THEN '⚠️ 사용자의 company가 빈 문자열'
        ELSE '✅ 정상'
    END as 상태,
    u.name as 요청자명,
    u.company as 사용자_company
FROM purchase_requests pr
LEFT JOIN users u ON pr.requester_id = u.id
WHERE pr.company IS NULL OR pr.company = '' OR pr.company = 'default_company'
ORDER BY pr.id;

-- ============================================================================
-- 🔍 추가 검증 쿼리
-- ============================================================================

-- 회사별 구매요청 분포 확인
SELECT
    company,
    COUNT(*) as 구매요청_수,
    COUNT(DISTINCT requester_id) as 요청자_수,
    SUM(amount) as 총_금액,
    MIN(created_at) as 최초_요청일,
    MAX(created_at) as 최근_요청일
FROM purchase_requests
WHERE company IS NOT NULL AND company != ''
GROUP BY company
ORDER BY 구매요청_수 DESC;

-- 역할별 구매요청 현황
SELECT
    u.role as 역할,
    u.company as 회사,
    COUNT(pr.id) as 구매요청_수,
    COUNT(DISTINCT u.id) as 사용자_수
FROM purchase_requests pr
INNER JOIN users u ON pr.requester_id = u.id
GROUP BY u.role, u.company
ORDER BY u.company, u.role;

-- ============================================================================
-- 📝 실행 가이드
-- ============================================================================
-- 1. STEP 1을 실행하여 업데이트할 레코드 수 확인
-- 2. STEP 2를 실행하여 실제 업데이트될 데이터 확인
-- 3. 문제가 없다면 STEP 3 실행 (실제 업데이트)
-- 4. STEP 4로 업데이트 결과 확인
-- 5. STEP 5로 문제가 있는 레코드 확인
--
-- ⚠️ 주의사항:
-- - STEP 3은 실제 데이터를 변경합니다
-- - Railway 프로덕션 환경에서는 신중하게 실행하세요
-- - 가능하면 백업 후 실행을 권장합니다
-- ============================================================================
