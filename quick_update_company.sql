-- ============================================================================
-- 🚀 빠른 업데이트 (한 줄 실행용)
-- ============================================================================
-- Railway Console이나 pgAdmin에서 바로 복사-붙여넣기하여 실행하세요
-- ============================================================================

-- 1️⃣ 먼저 확인 (얼마나 업데이트될지 체크)
SELECT COUNT(*) as "업데이트될_레코드_수" FROM purchase_requests WHERE company IS NULL OR company = '' OR company = 'default_company';

-- 2️⃣ 업데이트 실행 (위의 결과가 괜찮으면 실행)
UPDATE purchase_requests pr SET company = u.company, updated_at = NOW() FROM users u WHERE pr.requester_id = u.id AND (pr.company IS NULL OR pr.company = '' OR pr.company = 'default_company') AND u.company IS NOT NULL;

-- 3️⃣ 결과 확인
SELECT COUNT(*) as "업데이트_완료_수" FROM purchase_requests WHERE company IS NOT NULL AND company != '' AND updated_at >= NOW() - INTERVAL '1 minute';

-- ============================================================================
-- 📋 Railway Console 실행 방법:
-- ============================================================================
-- 1. Railway Dashboard → brandflow-backend-production → Data 탭
-- 2. "Query" 버튼 클릭
-- 3. 위의 쿼리를 하나씩 복사하여 실행
--
-- 또는 pgAdmin 실행 방법:
-- 1. pgAdmin에서 brandflow DB 연결
-- 2. Query Tool 열기 (Tools → Query Tool)
-- 3. 위의 쿼리를 순서대로 복사-붙여넣기하여 실행
-- ============================================================================
