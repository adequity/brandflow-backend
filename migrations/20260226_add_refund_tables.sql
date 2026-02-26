-- 캠페인 취소/환불 기능 마이그레이션 SQL
-- 실행: psycopg2 또는 pgAdmin4에서 직접 실행

-- 1. campaigns 테이블에 취소/환불 컬럼 추가
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP NULL;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS cancelled_by INTEGER NULL REFERENCES users(id);
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS cancellation_reason TEXT NULL;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS refund_amount NUMERIC(12, 2) DEFAULT 0 NULL;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS is_refunded BOOLEAN DEFAULT FALSE NULL;

-- 2. posts 테이블에 취소/환불 컬럼 추가
ALTER TABLE posts ADD COLUMN IF NOT EXISTS is_cancelled BOOLEAN DEFAULT FALSE NULL;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS refund_amount FLOAT DEFAULT 0 NULL;

-- 3. campaign_refunds 테이블 생성
CREATE TABLE IF NOT EXISTS campaign_refunds (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    refund_type VARCHAR(20) NOT NULL,
    refund_amount NUMERIC(12, 2) NOT NULL,
    original_amount NUMERIC(12, 2) NOT NULL,
    refund_reason TEXT NULL,
    status VARCHAR(20) DEFAULT '환불대기',
    requested_by INTEGER NOT NULL REFERENCES users(id),
    approved_by INTEGER NULL REFERENCES users(id),
    approved_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    cancel_invoice_url VARCHAR(500) NULL,
    cancel_invoice_name VARCHAR(200) NULL,
    cancel_invoice_size INTEGER NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_campaign_refunds_campaign_id ON campaign_refunds(campaign_id);

-- 4. post_refunds 테이블 생성
CREATE TABLE IF NOT EXISTS post_refunds (
    id SERIAL PRIMARY KEY,
    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    refund_type VARCHAR(20) NOT NULL,
    refund_amount NUMERIC(12, 2) NOT NULL,
    original_budget NUMERIC(12, 2) NOT NULL,
    refund_reason TEXT NULL,
    status VARCHAR(20) DEFAULT '환불대기',
    requested_by INTEGER NOT NULL REFERENCES users(id),
    approved_by INTEGER NULL REFERENCES users(id),
    approved_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    cancel_invoice_url VARCHAR(500) NULL,
    cancel_invoice_name VARCHAR(200) NULL,
    cancel_invoice_size INTEGER NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_post_refunds_post_id ON post_refunds(post_id);
CREATE INDEX IF NOT EXISTS idx_post_refunds_campaign_id ON post_refunds(campaign_id);
