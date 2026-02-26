# BrandFlow Backend - Claude 개발 가이드

## 기술 스택
- FastAPI + SQLAlchemy (async) + PostgreSQL (Railway)
- 인증: JWT (python-jose)
- DB 프록시: maglev.proxy.rlwy.net:32077

## 유저 Role 체계 (절대 기준)

모든 role 값은 **대문자 영문**으로 통일. DB, API, 프론트 모두 동일한 값 사용.

| Role 값 | 설명 | 권한 범위 |
|---------|------|----------|
| `SUPER_ADMIN` | 최고 관리자 | 전체 시스템 |
| `AGENCY_ADMIN` | 대행사 어드민 | 같은 company 내 모든 리소스 |
| `TEAM_LEADER` | 팀 리더 | 본인 + 팀원(team_leader_id) 캠페인 |
| `STAFF` | 직원 | 본인 생성/담당 캠페인만 |
| `CLIENT` | 클라이언트 | 본인 캠페인 조회/승인만 |

### 직원 선택 가능 역할 (캠페인 담당자 지정 시)
AGENCY_ADMIN이 캠페인 담당자로 지정 가능한 role: `STAFF`, `TEAM_LEADER`, `AGENCY_ADMIN`

### Role enum 정의 위치
- 백엔드: `app/models/user.py` → `UserRole(str, enum.Enum)`
- 프론트: `src/utils/permissions.js` → `ROLES` 객체

### 주의사항
- API 파라미터로 role 전달 시 반드시 대문자 사용 (예: `viewerRole=AGENCY_ADMIN`)
- 소문자(`agency_admin`) 전송 금지 - 백엔드에서 `.upper()` 정규화하지만 원칙은 대문자
- DB에 저장된 role 값도 항상 대문자 (`SUPER_ADMIN`, `AGENCY_ADMIN` 등)

## 회사(company) 기반 필터링
- AGENCY_ADMIN: `User.company == current_user.company`로 같은 회사 리소스만 접근
- 백엔드에서 필터링 완료 후 프론트에서 중복 필터링 하지 않음
- company 값은 DB 원본 그대로 사용 (정규화 비교 불필요)

## 캠페인 권한 요약
| 동작 | SUPER_ADMIN | AGENCY_ADMIN | TEAM_LEADER | STAFF | CLIENT |
|------|:-----------:|:------------:|:-----------:|:-----:|:------:|
| 생성 | O | O (대리 생성 가능) | O | O | X |
| 조회 | 전체 | 같은 회사 | 본인+팀원 | 본인 | 본인 |
| 수정 | 전체 | 같은 회사 | 본인+팀원 | 본인 | 본인 |
| 삭제 | O | O | O | X | X |

## DB 테이블 구조 (Railway PostgreSQL)

### 핵심 테이블

#### users
| Column | Type | 설명 |
|--------|------|------|
| id | integer PK | |
| name | varchar | 사용자명 |
| email | varchar UNIQUE | 로그인 이메일 |
| hashed_password | varchar | bcrypt 해시 |
| role | ENUM(UserRole) | SUPER_ADMIN/AGENCY_ADMIN/TEAM_LEADER/STAFF/CLIENT |
| company | varchar | 소속 회사 (company 기반 필터링 핵심) |
| contact | varchar | 연락처 |
| incentive_rate | float | 인센티브 비율 |
| status | ENUM(UserStatus) | ACTIVE/INACTIVE/BANNED |
| is_active | boolean | 활성 여부 |
| team_name | varchar | 팀명 |
| team_leader_id | integer FK→users | 소속 팀리더 ID |
| assigned_staff_id | integer FK→users | CLIENT 담당 직원 ID |
| client_company_name | text | 클라이언트 실제 회사명 |
| client_business_number | text | 사업자번호 |
| client_ceo_name | text | 대표자명 |
| client_company_address | text | 회사 주소 |
| client_business_type | text | 업종 |
| client_business_item | text | 업태 |

#### campaigns
| Column | Type | 설명 |
|--------|------|------|
| id | integer PK | |
| name | varchar | 캠페인명 |
| description | text | 설명 |
| client_company | varchar | 클라이언트 회사명 (표시용) |
| budget | float | 매출(예산) |
| cost | numeric | 비용 |
| margin | numeric | 마진 |
| margin_rate | numeric | 마진율 |
| estimated_cost | numeric | 예상 비용 |
| start_date | timestamp | 시작일 |
| end_date | timestamp | 종료일 |
| project_due_date | timestamp | 프로젝트 마감일 |
| status | ENUM | ACTIVE 등 |
| executionstatus | text | 실행 상태 |
| creator_id | integer FK→users | 생성자 |
| staff_id | integer FK→users | 담당 직원 (STAFF/TEAM_LEADER) |
| client_user_id | integer FK→users | 클라이언트 유저 |
| company | varchar | 소속 회사 |
| chat_content | text | 카톡 내용 |
| chat_summary | text | 카톡 요약 |
| chat_attachments | text | 카톡 첨부 |
| chat_images | text | 카톡 이미지 |

#### posts (업무)
| Column | Type | 설명 |
|--------|------|------|
| id | integer PK | |
| title | text | 업무명 |
| work_type | varchar | 업무 유형 |
| topic_status | varchar | 주제 상태 |
| outline | text | 개요 |
| outline_status | varchar | 개요 상태 |
| images | json | 이미지 목록 |
| published_url | text | 게시 URL |
| start_date / due_date | varchar | 시작/마감일 (문자열) |
| start_datetime / due_datetime | timestamp | 시작/마감 일시 |
| campaign_id | integer FK→campaigns | 소속 캠페인 |
| assigned_user_id | integer FK→users | 담당자 |
| product_id | integer FK→products | 관련 상품 |
| quantity | integer | 수량 |
| budget | float | 업무 매출 |
| cost | float | 비용 |
| product_cost | float | 상품 비용 |
| product_name | varchar | 상품명 |
| company | varchar | 소속 회사 |
| order_request_status | varchar | 발주 상태 |
| order_request_id | integer | 발주 요청 ID |
| invoice_issued | boolean | 계산서 발행 |
| payment_completed | boolean | 입금 완료 |
| invoice_due_date | timestamp | 계산서 발행일 |
| payment_due_date | timestamp | 입금 예정일 |
| reject_reason | text | 반려 사유 |

### 부가 테이블

#### purchase_requests (구매요청)
- requester_id → users, campaign_id → campaigns
- status: ENUM (대기/승인/반려 등)
- amount, quantity, vendor, priority, due_date

#### order_requests (발주요청)
- post_id → posts, user_id → users, campaign_id → campaigns
- cost_price, resource_type, status

#### products (상품)
- name, price, cost, selling_price, category, sku, company

#### sales (매출)
- employee_id → users, product_id → products
- client_name, quantity, unit_price, total_amount, commission

#### incentives / monthly_incentives (인센티브)
- user_id → users
- year, month, 각종 매출/비용/마진/인센티브 필드

#### campaign_contracts (계약서)
- campaign_id → campaigns
- file_url, file_name, file_size

#### campaign_costs (캠페인 비용)
- campaign_id → campaigns
- cost_type, amount, receipt_url, vendor_name

#### board_posts / board_post_attachments (게시판)
- author_id → users, company 기반 필터링
- post_type, is_notice, is_popup

#### work_types (업무유형)
- name, color, company 기반

#### telegram_notification_logs / user_telegram_settings (텔레그램)
- 알림 발송 기록 및 사용자별 텔레그램 설정

#### system_settings / company_settings (시스템 설정)
- 전체 시스템 및 회사별 설정 key-value

#### company_logos
- company_id, logo_url

#### 기타 (WaitPlay 관련)
- qr_codes, queue_entries, landing_page_settings, waitplay_users, game_assets

## API 엔드포인트 맵

| Prefix | 파일 | 설명 |
|--------|------|------|
| `/api/auth` | `auth.py` | 로그인/로그아웃/토큰 |
| `/api/users` | `users.py` | 사용자 CRUD, 직원/클라이언트 목록 |
| `/api/campaigns` | `campaigns.py` | 캠페인 CRUD, posts(업무), staff-list, client-list, 계약서, 발주 |
| `/api/purchase-requests` | `purchase_requests.py` | 구매요청 CRUD, 승인/반려 |
| `/api/dashboard` | `dashboard.py` | 대시보드 통계 |
| `/api/products` | `products.py` | 상품 관리 |
| `/api/work-types` | `work_types.py` | 업무유형 관리 |
| `/api/files` | `file_upload.py` | 파일 업로드 |
| `/api/export` | `export.py` | 엑셀/PDF 내보내기 |
| `/api/company` | `company_logo.py` | 회사 로고 |
| `/api/notifications` | `notifications.py` | 알림 |
| `/api/admin` | `admin.py` | 관리자 전용 |

## 배포 환경

| 항목 | URL |
|------|-----|
| 백엔드 (Railway) | `https://brandflow-backend-production-99ae.up.railway.app` |
| 프론트엔드 (Netlify) | `https://brandflo.netlify.app` |
| DB (Railway PostgreSQL) | `maglev.proxy.rlwy.net:32077` / DB: `railway` |

## 핵심 파일 경로

### 백엔드
- 엔트리포인트: `main.py`
- 설정: `app/core/config.py`
- 라우터 등록: `app/api/router.py`
- 모델: `app/models/` (user.py, campaign.py, post.py 등)
- API 엔드포인트: `app/api/endpoints/` (campaigns.py가 가장 큼)
- 스키마: `app/schemas/`
- 서비스: `app/services/`
- 보안: `app/core/security.py`
- DB 연결: `app/db/database.py`
