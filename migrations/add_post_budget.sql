-- Migration: Add budget column to posts table
-- Date: 2025-01-23
-- Description: 각 업무(Post)별로 매출 예산을 관리하기 위한 budget 컬럼 추가

-- posts 테이블에 budget 컬럼 추가
ALTER TABLE posts ADD COLUMN budget FLOAT DEFAULT 0.0;

-- 기존 데이터 처리:
-- 1) 기존 posts는 budget이 0.0으로 초기화됨
-- 2) 필요시 수동으로 각 post의 budget을 입력
-- 3) 또는 캠페인의 budget을 posts 개수로 나누어 균등 분배 가능:
--    UPDATE posts p
--    SET budget = (
--        SELECT c.budget / COUNT(*)
--        FROM campaigns c
--        JOIN posts p2 ON p2.campaign_id = c.id
--        WHERE c.id = p.campaign_id
--        GROUP BY c.id
--    )
--    WHERE p.campaign_id IS NOT NULL;

COMMENT ON COLUMN posts.budget IS '포스트별 매출 예산 - 캠페인 전체 매출은 모든 posts의 budget 합계';
