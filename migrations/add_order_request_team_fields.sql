-- OrderRequest 테이블에 팀/역할 정보 필드 추가 마이그레이션
-- 실행 날짜: 2025-01-23
-- 목적: 성능 최적화를 위한 denormalization (JOIN 제거)

-- 1. company 컬럼 추가 (요청자 회사)
ALTER TABLE order_requests
ADD COLUMN IF NOT EXISTS company VARCHAR(200) DEFAULT 'default_company';

-- 2. requester_role 컬럼 추가 (요청자 역할)
ALTER TABLE order_requests
ADD COLUMN IF NOT EXISTS requester_role VARCHAR(50);

-- 3. team_leader_id 컬럼 추가 (요청자의 팀장 ID)
ALTER TABLE order_requests
ADD COLUMN IF NOT EXISTS team_leader_id INTEGER;

-- 4. team_leader_id에 Foreign Key 제약 추가
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_order_requests_team_leader'
    ) THEN
        ALTER TABLE order_requests
        ADD CONSTRAINT fk_order_requests_team_leader
        FOREIGN KEY (team_leader_id) REFERENCES users(id) ON DELETE SET NULL;
    END IF;
END $$;

-- 5. 인덱스 생성 (성능 최적화)
CREATE INDEX IF NOT EXISTS ix_order_requests_company ON order_requests(company);
CREATE INDEX IF NOT EXISTS ix_order_requests_requester_role ON order_requests(requester_role);
CREATE INDEX IF NOT EXISTS ix_order_requests_team_leader_id ON order_requests(team_leader_id);

-- 6. 기존 데이터 백필: user 정보에서 company, requester_role, team_leader_id 채우기
UPDATE order_requests
SET
    company = COALESCE(users.company, 'default_company'),
    requester_role = users.role::text,
    team_leader_id = users.team_leader_id
FROM users
WHERE order_requests.user_id = users.id
AND (
    order_requests.company IS NULL
    OR order_requests.requester_role IS NULL
    OR (order_requests.team_leader_id IS NULL AND users.team_leader_id IS NOT NULL)
);

-- 7. 확인 쿼리
SELECT
    COUNT(*) as total_orders,
    COUNT(CASE WHEN company IS NOT NULL THEN 1 END) as orders_with_company,
    COUNT(CASE WHEN requester_role IS NOT NULL THEN 1 END) as orders_with_role,
    COUNT(CASE WHEN team_leader_id IS NOT NULL THEN 1 END) as orders_with_team_leader,
    COUNT(CASE WHEN company IS NULL THEN 1 END) as orders_missing_company,
    COUNT(CASE WHEN requester_role IS NULL THEN 1 END) as orders_missing_role
FROM order_requests;
