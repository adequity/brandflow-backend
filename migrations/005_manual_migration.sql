-- Migration 005: Add Team Leader and Cost System
-- Execute this manually in Railway PostgreSQL console

-- 1. users 테이블에 팀 관련 필드 추가
ALTER TABLE users ADD COLUMN IF NOT EXISTS team_id INTEGER;
ALTER TABLE users ADD COLUMN IF NOT EXISTS team_name VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS team_leader_id INTEGER;

-- team_leader_id 외래키 제약조건
ALTER TABLE users ADD CONSTRAINT fk_users_team_leader
    FOREIGN KEY (team_leader_id) REFERENCES users(id) ON DELETE SET NULL;

-- 2. campaigns 테이블에 원가 관련 필드 추가
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS cost NUMERIC(12, 2) DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS margin NUMERIC(12, 2) DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS margin_rate NUMERIC(5, 2) DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS estimated_cost NUMERIC(12, 2) DEFAULT 0;

-- 일정 관련 필드
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS invoice_due_date TIMESTAMP;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS payment_due_date TIMESTAMP;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS project_due_date TIMESTAMP;

-- 3. campaign_costs 테이블 생성
CREATE TABLE IF NOT EXISTS campaign_costs (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    cost_type VARCHAR(50) NOT NULL,
    description TEXT,
    amount NUMERIC(12, 2) NOT NULL,
    receipt_url TEXT,
    vendor_name VARCHAR(200),
    is_approved BOOLEAN DEFAULT false,
    approved_by INTEGER REFERENCES users(id),
    approved_at TIMESTAMP,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- campaign_costs 인덱스
CREATE INDEX IF NOT EXISTS idx_campaign_costs_campaign ON campaign_costs(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaign_costs_type ON campaign_costs(cost_type);

-- 4. incentives 테이블 생성
CREATE TABLE IF NOT EXISTS incentives (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,

    -- 매출 데이터
    personal_revenue NUMERIC(12, 2) DEFAULT 0,
    team_revenue NUMERIC(12, 2) DEFAULT 0,
    company_revenue NUMERIC(12, 2) DEFAULT 0,

    -- 원가 데이터
    personal_cost NUMERIC(12, 2) DEFAULT 0,
    team_cost NUMERIC(12, 2) DEFAULT 0,
    company_cost NUMERIC(12, 2) DEFAULT 0,

    -- 이익 데이터
    personal_margin NUMERIC(12, 2) DEFAULT 0,
    team_margin NUMERIC(12, 2) DEFAULT 0,
    company_margin NUMERIC(12, 2) DEFAULT 0,

    -- 마진율
    personal_margin_rate NUMERIC(5, 2) DEFAULT 0,
    team_margin_rate NUMERIC(5, 2) DEFAULT 0,
    company_margin_rate NUMERIC(5, 2) DEFAULT 0,

    -- 인센티브 금액
    personal_incentive NUMERIC(12, 2) DEFAULT 0,
    team_incentive NUMERIC(12, 2) DEFAULT 0,
    bonus NUMERIC(12, 2) DEFAULT 0,
    total_incentive NUMERIC(12, 2) DEFAULT 0,

    -- 인센티브율
    personal_rate NUMERIC(5, 2) DEFAULT 10.0,
    team_rate NUMERIC(5, 2) DEFAULT 15.0,

    -- 성과 지표
    campaign_count INTEGER DEFAULT 0,
    completed_campaign_count INTEGER DEFAULT 0,
    completion_rate NUMERIC(5, 2) DEFAULT 0,

    -- 상태
    status VARCHAR(20) DEFAULT 'draft',
    confirmed_by INTEGER REFERENCES users(id),
    confirmed_at TIMESTAMP,
    paid_at TIMESTAMP,

    -- 메타
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- incentives 유니크 제약조건 및 인덱스
CREATE UNIQUE INDEX IF NOT EXISTS uq_incentives_user_year_month ON incentives(user_id, year, month);
CREATE INDEX IF NOT EXISTS idx_incentives_user_date ON incentives(user_id, year, month);
CREATE INDEX IF NOT EXISTS idx_incentives_status ON incentives(status);

-- 5. incentive_rules 테이블 생성
CREATE TABLE IF NOT EXISTS incentive_rules (
    id SERIAL PRIMARY KEY,
    role VARCHAR(50) NOT NULL,

    -- 기본 인센티브율
    personal_rate NUMERIC(5, 2) DEFAULT 10.0,
    team_rate NUMERIC(5, 2) DEFAULT 15.0,
    company_rate NUMERIC(5, 2) DEFAULT 5.0,

    -- 성과 보너스 기준
    bonus_threshold_margin NUMERIC(12, 2),
    bonus_amount NUMERIC(12, 2),
    bonus_completion_rate NUMERIC(5, 2),

    -- 활성화
    is_active BOOLEAN DEFAULT true,
    effective_from DATE,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 기본 인센티브 정책 데이터 삽입 (중복 방지)
INSERT INTO incentive_rules (role, personal_rate, team_rate, company_rate, bonus_threshold_margin, bonus_amount, bonus_completion_rate, is_active)
SELECT 'STAFF', 10.0, 0, 0, 3000000, 200000, 90.0, true
WHERE NOT EXISTS (SELECT 1 FROM incentive_rules WHERE role = 'STAFF');

INSERT INTO incentive_rules (role, personal_rate, team_rate, company_rate, bonus_threshold_margin, bonus_amount, bonus_completion_rate, is_active)
SELECT 'TEAM_LEADER', 10.0, 15.0, 0, 5000000, 500000, 85.0, true
WHERE NOT EXISTS (SELECT 1 FROM incentive_rules WHERE role = 'TEAM_LEADER');

INSERT INTO incentive_rules (role, personal_rate, team_rate, company_rate, bonus_threshold_margin, bonus_amount, bonus_completion_rate, is_active)
SELECT 'AGENCY_ADMIN', 5.0, 0, 10.0, 20000000, 2000000, 80.0, true
WHERE NOT EXISTS (SELECT 1 FROM incentive_rules WHERE role = 'AGENCY_ADMIN');

-- 완료 메시지
SELECT 'Migration 005 completed successfully!' AS status;
