-- =====================================================
-- 상태값 획일화 마이그레이션 SQL
-- =====================================================
-- 목적: AGENCY_ADMIN과 CLIENT 간 상태값 통일
-- 실행 전 백업 권장: pg_dump 또는 Railway 스냅샷
-- =====================================================

-- 1단계: 현재 상태값 확인 (실행 전)
SELECT 'topic_status 현황' as info, topic_status, COUNT(*) as count
FROM posts
WHERE topic_status IS NOT NULL
GROUP BY topic_status
ORDER BY count DESC;

SELECT 'outline_status 현황' as info, outline_status, COUNT(*) as count
FROM posts
WHERE outline_status IS NOT NULL
GROUP BY outline_status
ORDER BY count DESC;

-- 2단계: topic_status 마이그레이션
UPDATE posts
SET topic_status = CASE
    WHEN topic_status = '대기' THEN '주제 승인 대기'
    WHEN topic_status = '승인' THEN '주제 승인'
    WHEN topic_status = '주제승인' THEN '주제 승인'
    WHEN topic_status = '거절' THEN '주제 반려'
    WHEN topic_status = '반려' THEN '주제 반려'
    -- 이미 올바른 형식인 경우 유지
    WHEN topic_status IN ('주제 승인 대기', '주제 승인', '주제 반려') THEN topic_status
    ELSE topic_status
END
WHERE topic_status IS NOT NULL;

-- 3단계: outline_status 마이그레이션
-- "주제 승인", "주제 반려" 같은 잘못된 값들을 목차로 수정
UPDATE posts
SET outline_status = CASE
    WHEN outline_status = '대기' THEN '목차 승인 대기'
    WHEN outline_status = '승인' THEN '목차 승인'
    WHEN outline_status = '목차승인' THEN '목차 승인'
    WHEN outline_status = '거절' THEN '목차 반려'
    WHEN outline_status = '반려' THEN '목차 반려'
    -- 잘못 저장된 주제 관련 값들을 목차로 변환
    WHEN outline_status = '주제 승인 대기' THEN '목차 승인 대기'
    WHEN outline_status = '주제 승인' THEN '목차 승인'
    WHEN outline_status = '주제 반려' THEN '목차 반려'
    -- 이미 올바른 형식인 경우 유지
    WHEN outline_status IN ('목차 승인 대기', '목차 승인', '목차 반려') THEN outline_status
    ELSE outline_status
END
WHERE outline_status IS NOT NULL;

-- 4단계: 마이그레이션 결과 확인
SELECT 'topic_status 마이그레이션 후' as info, topic_status, COUNT(*) as count
FROM posts
WHERE topic_status IS NOT NULL
GROUP BY topic_status
ORDER BY count DESC;

SELECT 'outline_status 마이그레이션 후' as info, outline_status, COUNT(*) as count
FROM posts
WHERE outline_status IS NOT NULL
GROUP BY outline_status
ORDER BY count DESC;

-- 5단계: 샘플 데이터 확인
SELECT id, title, topic_status, outline_status
FROM posts
WHERE topic_status IS NOT NULL OR outline_status IS NOT NULL
ORDER BY id DESC
LIMIT 10;

-- =====================================================
-- 마이그레이션 완료!
-- =====================================================
