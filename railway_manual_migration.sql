-- Railway 수동 마이그레이션: 텔레그램 알림 로그 외래키 nullable 설정
-- 실행 전 백업 권장

-- 1. 현재 테이블 구조 확인
\d telegram_notification_logs;

-- 2. 외래키 제약조건 nullable로 변경
ALTER TABLE telegram_notification_logs
ALTER COLUMN post_id DROP NOT NULL;

ALTER TABLE telegram_notification_logs
ALTER COLUMN campaign_id DROP NOT NULL;

-- 3. 변경사항 확인
\d telegram_notification_logs;

-- 4. 테스트 레코드 삽입 (선택사항)
INSERT INTO telegram_notification_logs
(user_id, notification_type, message_content, is_sent, created_at)
VALUES
(1, 'test', '마이그레이션 테스트 메시지', true, NOW());

-- 5. 테스트 레코드 삭제 (선택사항)
DELETE FROM telegram_notification_logs
WHERE notification_type = 'test' AND message_content = '마이그레이션 테스트 메시지';

-- 6. 마이그레이션 히스토리 업데이트 (Alembic 버전 테이블)
INSERT INTO alembic_version (version_num) VALUES ('bbf3e8512c20')
ON CONFLICT (version_num) DO NOTHING;