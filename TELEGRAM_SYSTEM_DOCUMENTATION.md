# 텔레그램 알림 시스템 완전 문서

## 📋 목차
1. [시스템 개요](#시스템-개요)
2. [아키텍처 구조](#아키텍처-구조)
3. [데이터베이스 모델](#데이터베이스-모델)
4. [핵심 서비스](#핵심-서비스)
5. [API 엔드포인트](#api-엔드포인트)
6. [스케줄러 동작 방식](#스케줄러-동작-방식)
7. [날짜 처리 로직](#날짜-처리-로직)
8. [전체 코드](#전체-코드)

---

## 시스템 개요

**BrandFlow 텔레그램 알림 시스템**은 캠페인 마감일이 임박할 때 사용자에게 자동으로 텔레그램 메시지를 발송하는 시스템입니다.

### 주요 기능
- ✅ 사용자별 텔레그램 설정 관리
- ✅ 마감일 임박 자동 알림 (사용자 설정 기반)
- ✅ 알림 시간 커스터마이징 (기본: 오전 9시)
- ✅ 마감 며칠 전 알림 설정 (기본: 2일)
- ✅ 알림 발송 로그 기록
- ✅ 테스트 메시지 전송
- ✅ 관리자 통계 대시보드

### 지원 사용자 역할
- ❌ **CLIENT**: 알림 불가 (고객사는 대행사 운영과 무관)
- ✅ **STAFF**: 본인이 생성한 캠페인의 마감일 알림
- ✅ **TEAM_LEADER**: 본인 + 팀원들의 캠페인 마감일 알림
- ✅ **AGENCY_ADMIN**: 회사 모든 캠페인 마감일 알림
- ✅ **SUPER_ADMIN**: 모든 캠페인 마감일 알림

---

## 아키텍처 구조

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Telegram Notification System                │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │  API Endpoints   │      │   Scheduler      │            │
│  │                  │      │                  │            │
│  │ - 설정 CRUD      │      │ - 15분마다 체크  │            │
│  │ - 테스트 발송    │      │ - 알림 시간 확인 │            │
│  │ - 로그 조회      │      │ - 자동 발송      │            │
│  │ - 통계           │      │ - 로그 기록      │            │
│  └────────┬─────────┘      └────────┬─────────┘            │
│           │                         │                       │
│           └────────┬────────────────┘                       │
│                    ▼                                         │
│         ┌──────────────────────┐                            │
│         │   Telegram Service   │                            │
│         │                      │                            │
│         │ - send_message()     │                            │
│         │ - get_chat_info()    │                            │
│         │ - send_reminder()    │                            │
│         │ - send_test()        │                            │
│         └──────────┬───────────┘                            │
│                    │                                         │
└────────────────────┼─────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  Telegram Bot API     │
         │  (api.telegram.org)   │
         └───────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │    User's Telegram    │
         │      Client App       │
         └───────────────────────┘
```

### 컴포넌트 설명

| 컴포넌트 | 역할 | 파일 위치 |
|---------|------|----------|
| **API Endpoints** | 텔레그램 설정 CRUD, 테스트, 통계 | `app/api/endpoints/telegram_settings.py` |
| **Scheduler** | 주기적으로 마감일 체크 및 알림 발송 | `app/services/telegram_scheduler.py` |
| **Telegram Service** | 텔레그램 API 호출 로직 | `app/services/telegram_service.py` |
| **Database Models** | 설정, 로그 저장 | `app/models/user_telegram_setting.py` |
| **Schemas** | Pydantic 검증 모델 | `app/schemas/telegram_setting.py` |
| **Date Utils** | 날짜 파싱 및 알림 판단 | `app/utils/date_utils.py` |

---

## 데이터베이스 모델

### 1. UserTelegramSetting (사용자 텔레그램 설정)

**테이블명**: `user_telegram_settings`

```python
class UserTelegramSetting(Base, TimestampMixin):
    """사용자별 텔레그램 알림 설정"""
    __tablename__ = "user_telegram_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    telegram_chat_id = Column(String(100), nullable=False, index=True)
    telegram_username = Column(String(100), nullable=True)

    # 알림 설정
    is_enabled = Column(Boolean, default=True, nullable=False)
    days_before_due = Column(Integer, default=2, nullable=False)  # 마감일 며칠 전 알림
    notification_time = Column(String(5), default="09:00", nullable=False)  # 알림 시간 (HH:MM)

    # 마지막 알림 기록
    last_notification_at = Column(DateTime, nullable=True)

    # 관계
    user = relationship("User", back_populates="telegram_setting")
```

**컬럼 설명**:
| 컬럼 | 타입 | 설명 | 기본값 |
|-----|------|------|-------|
| `id` | Integer | Primary Key | AUTO |
| `user_id` | Integer | 사용자 ID (FK, UNIQUE) | - |
| `telegram_chat_id` | String(100) | 텔레그램 채팅 ID | - |
| `telegram_username` | String(100) | 텔레그램 사용자명 (선택) | NULL |
| `is_enabled` | Boolean | 알림 활성화 여부 | true |
| `days_before_due` | Integer | 마감일 며칠 전 알림 | 2 |
| `notification_time` | String(5) | 알림 시간 (HH:MM) | "09:00" |
| `last_notification_at` | DateTime | 마지막 알림 발송 시각 | NULL |

### 2. TelegramNotificationLog (알림 발송 로그)

**테이블명**: `telegram_notification_logs`

```python
class TelegramNotificationLog(Base, TimestampMixin):
    """텔레그램 알림 발송 로그"""
    __tablename__ = "telegram_notification_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)  # 테스트 메시지는 None 가능
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)

    # 알림 정보
    notification_type = Column(String(50), default="due_date_reminder", nullable=False)
    message_content = Column(String(1000), nullable=False)
    telegram_chat_id = Column(String(100), nullable=False)

    # 발송 결과
    is_sent = Column(Boolean, default=False, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(String(500), nullable=True)
    telegram_message_id = Column(String(100), nullable=True)

    # 관계
    user = relationship("User")
    post = relationship("Post")
    campaign = relationship("Campaign")
```

**컬럼 설명**:
| 컬럼 | 타입 | 설명 |
|-----|------|------|
| `id` | Integer | Primary Key |
| `user_id` | Integer | 사용자 ID (FK) |
| `post_id` | Integer | Post ID (FK, NULL 가능) |
| `campaign_id` | Integer | Campaign ID (FK, NULL 가능) |
| `notification_type` | String(50) | 알림 타입 (due_date_reminder, test_message) |
| `message_content` | String(1000) | 전송된 메시지 내용 |
| `telegram_chat_id` | String(100) | 텔레그램 채팅 ID |
| `is_sent` | Boolean | 전송 성공 여부 |
| `sent_at` | DateTime | 전송 완료 시각 |
| `error_message` | String(500) | 에러 메시지 (실패 시) |
| `telegram_message_id` | String(100) | 텔레그램 메시지 ID |

---

## 핵심 서비스

### 1. TelegramService (텔레그램 API 서비스)

**파일**: `app/services/telegram_service.py`

#### 주요 메서드

##### `send_message(chat_id, message, parse_mode, disable_web_page_preview)`
텔레그램 메시지 전송

**Parameters**:
- `chat_id` (str): 텔레그램 채팅 ID
- `message` (str): 전송할 메시지 내용
- `parse_mode` (str): 메시지 포맷 (기본: "HTML")
- `disable_web_page_preview` (bool): 링크 미리보기 비활성화 (기본: True)

**Returns**:
```python
{
    "success": True/False,
    "message_id": "123456",  # 성공 시
    "error": "error message",  # 실패 시
    "error_code": "error_code"  # 실패 시
}
```

##### `get_chat_info(chat_id)`
채팅 정보 조회 (chat_id 유효성 검증용)

**Parameters**:
- `chat_id` (str): 텔레그램 채팅 ID

**Returns**:
```python
{
    "success": True/False,
    "data": {...},  # 성공 시 채팅 정보
    "error": "error message"  # 실패 시
}
```

##### `send_campaign_deadline_reminder(...)`
캠페인 마감일 알림 메시지 전송

**Parameters**:
- `chat_id` (str): 텔레그램 채팅 ID
- `user_name` (str): 사용자 이름
- `post_title` (str): 작업명
- `due_date` (str): 마감일
- `days_before` (int): 며칠 전 알림
- `work_type` (str, optional): 상품종류
- `product_name` (str, optional): 상품명

**메시지 형식**:
```
🚨 긴급 - 캠페인 마감일 알림

안녕하세요, 홍길동님!

📝 작업명: 인스타그램 피드 포스팅
📋 상품종류: 인플루언서
🔗 상품명: 나이키 운동화
📅 마감일: 2025-11-15 18:00
⏰남은 시간: 2일

마감일이 다가오고 있습니다. 작업 진행 상황을 확인해 주세요!

BrandFlow 알림 시스템
```

##### `send_test_message(chat_id, user_name)`
테스트 메시지 전송

---

### 2. TelegramScheduler (스케줄러)

**파일**: `app/services/telegram_scheduler.py`

#### 주요 메서드

##### `start()`
스케줄러 시작 (백그라운드 루프)

**동작**:
1. `self.running = True` 설정
2. 무한 루프 시작
3. 15분마다 `check_and_send_notifications()` 호출
4. 오류 발생 시 1분 후 재시도

##### `stop()`
스케줄러 중지

##### `check_and_send_notifications()`
마감일 임박 알림 확인 및 전송

**동작 프로세스**:
```
1. CLIENT 역할 제외한 활성 사용자 조회
   ↓
2. 각 사용자별로 루프:
   ├─ 사용자가 생성한 캠페인의 마감일 있는 posts 조회
   ├─ 각 post별로 알림 조건 체크:
   │  ├─ 오늘 이미 알림 보냈는지 확인 (중복 방지)
   │  ├─ 현재 시간이 알림 시간대인지 확인 (±2시간)
   │  └─ 마감일까지 days_before_due 이내인지 확인
   └─ 조건 만족 시 알림 전송
   ↓
3. 로그 저장 (성공/실패)
   ↓
4. last_notification_at 업데이트
```

##### `get_user_posts_with_upcoming_deadlines(db, user_id, days_before)`
사용자의 마감일 임박 posts 조회

**Parameters**:
- `db` (Session): 데이터베이스 세션
- `user_id` (int): 사용자 ID
- `days_before` (int): 며칠 전 알림 설정

**Returns**:
```python
[
    (post, campaign, days_left),  # Tuple[Post, Campaign, float]
    ...
]
```

**로직**:
1. 사용자가 생성한 캠페인의 posts 조회 (due_date 있는 것만)
2. 각 post의 due_date를 파싱 (`parse_due_datetime`)
3. `should_send_telegram_notification()` 함수로 알림 조건 판단
4. 조건 만족하는 posts만 반환

##### `send_deadline_notification(...)`
마감일 알림 전송

**Parameters**:
- `db` (Session): 데이터베이스 세션
- `user` (User): 사용자 객체
- `post` (Post): Post 객체
- `campaign` (Campaign): Campaign 객체
- `days_left` (float): 남은 일수
- `telegram_setting` (UserTelegramSetting): 텔레그램 설정

**동작**:
1. due_date 파싱 및 포맷팅
2. `telegram_service.send_campaign_deadline_reminder()` 호출
3. TelegramNotificationLog 생성 및 저장
4. 성공 시 `last_notification_at` 업데이트

##### `is_notification_time(notification_time)`
현재 시간이 알림 시간인지 확인

**로직**:
- 알림 시간 ±2시간 범위 내에 있으면 True
- 예: 알림 시간 09:00 → 07:00~11:00 사이면 True

---

## API 엔드포인트

**Router**: `/api/telegram-settings`

### 1. 사용자 설정 관리

#### `GET /my-setting`
현재 사용자의 텔레그램 설정 조회

**Response**:
```json
{
  "id": 1,
  "user_id": 5,
  "telegram_chat_id": "123456789",
  "telegram_username": "john_doe",
  "is_enabled": true,
  "days_before_due": 2,
  "notification_time": "09:00",
  "last_notification_at": "2025-10-28T09:00:00",
  "created_at": "2025-10-01T10:00:00",
  "updated_at": "2025-10-28T09:00:00"
}
```

#### `POST /my-setting`
텔레그램 설정 생성 또는 업데이트

**Request Body**:
```json
{
  "telegram_chat_id": "123456789",
  "telegram_username": "john_doe",
  "is_enabled": true,
  "days_before_due": 2,
  "notification_time": "09:00"
}
```

**Validation**:
- `telegram_chat_id`: 숫자 또는 @로 시작하는 문자열
- `notification_time`: HH:MM 형식 (00:00 ~ 23:59)
- `days_before_due`: 1 ~ 30 사이

**Response**: 생성/업데이트된 설정 객체

#### `PUT /my-setting`
텔레그램 설정 업데이트

**Request Body** (부분 업데이트 가능):
```json
{
  "is_enabled": false,
  "days_before_due": 3
}
```

#### `DELETE /my-setting`
텔레그램 설정 삭제

**Response**:
```json
{
  "message": "텔레그램 설정이 삭제되었습니다"
}
```

---

### 2. 테스트 및 로그

#### `POST /test`
텔레그램 테스트 메시지 전송

**Request Body**:
```json
{
  "message": "테스트 메시지입니다."
}
```

**Response** (성공):
```json
{
  "success": true,
  "message": "테스트 메시지가 성공적으로 전송되었습니다!",
  "telegram_message_id": "123456"
}
```

**Response** (실패):
```json
{
  "detail": "메시지 전송 실패: Invalid chat_id"
}
```

#### `GET /logs?limit=20&offset=0`
현재 사용자의 텔레그램 알림 로그 조회

**Query Parameters**:
- `limit` (int): 조회할 로그 수 (1~100, 기본: 20)
- `offset` (int): 조회 시작 위치 (기본: 0)

**Response**:
```json
[
  {
    "id": 1,
    "user_id": 5,
    "post_id": 10,
    "campaign_id": 2,
    "notification_type": "due_date_reminder",
    "message_content": "마감일 2일 전 알림: 인스타그램 피드 포스팅",
    "is_sent": true,
    "sent_at": "2025-10-28T09:00:00",
    "error_message": null,
    "created_at": "2025-10-28T09:00:00"
  }
]
```

---

### 3. 관리자 전용

#### `GET /stats`
텔레그램 알림 통계 (SUPER_ADMIN, AGENCY_ADMIN만)

**Response**:
```json
{
  "total_users_with_telegram": 50,
  "active_notifications": 45,
  "notifications_sent_today": 120,
  "notifications_failed_today": 5,
  "upcoming_deadlines": 30
}
```

#### `GET /admin/all-settings?page=1&size=20&is_enabled=true`
모든 사용자의 텔레그램 설정 조회 (관리자용)

**Query Parameters**:
- `page` (int): 페이지 번호 (기본: 1)
- `size` (int): 페이지당 항목 수 (1~100, 기본: 20)
- `is_enabled` (bool, optional): 활성화 여부 필터

**Response**:
```json
{
  "total": 50,
  "page": 1,
  "size": 20,
  "settings": [...]
}
```

#### `POST /test-deadline-notifications?force_all=false`
텔레그램 마감일 알림 테스트 (관리자용)

**Query Parameters**:
- `force_all` (bool): 모든 알림 시간대에서 강제 실행 (기본: false)

**Response**:
```json
{
  "success": true,
  "message": "텔레그램 마감일 알림 테스트가 완료되었습니다.",
  "force_all": false,
  "executed_at": "2025-10-28T10:30:00"
}
```

---

## 스케줄러 동작 방식

### 실행 주기
- **15분마다** 자동으로 마감일 체크 (`check_interval = 900`)
- 애플리케이션 시작 시 백그라운드로 자동 실행

### 알림 조건

#### 1. 사용자 필터링
```python
# 클라이언트 역할 제외 + 활성화된 텔레그램 설정 + 활성 사용자만
telegram_users = db.query(UserTelegramSetting).join(User).filter(
    and_(
        User.role != UserRole.CLIENT,
        UserTelegramSetting.is_enabled == True,
        User.is_active == True
    )
).all()
```

#### 2. 마감일 체크 로직
```python
# date_utils.should_send_telegram_notification() 함수 사용
should_send, days_left = should_send_telegram_notification(
    due_datetime=due_datetime,
    days_before_setting=days_before,  # 사용자 설정값
    current_time=now,
    grace_period_hours=12.0  # 마감 후 12시간까지 유예
)

# 알림 조건:
# 1. 마감 전: days_before_setting 일 이내
# 2. 마감 후: grace_period_hours 시간 이내
# 예: days_before_setting=2, grace_period=12시간
#     → 마감 2일 전 ~ 마감 후 12시간까지 알림
```

#### 3. 중복 발송 방지
```python
# 오늘 이미 알림을 보낸 적이 있는지 확인
existing_log = db.query(TelegramNotificationLog).filter(
    and_(
        TelegramNotificationLog.user_id == user.id,
        TelegramNotificationLog.post_id == post.id,
        TelegramNotificationLog.notification_type == "due_date_reminder",
        TelegramNotificationLog.is_sent == True,
        func.date(TelegramNotificationLog.created_at) == func.date(datetime.utcnow())
    )
).first()

if existing_log:
    continue  # 이미 전송됨, 스킵
```

#### 4. 알림 시간 체크
```python
# ±2시간 범위 내에서 알림 시간으로 판단
def is_notification_time(self, notification_time: str) -> bool:
    hour, minute = map(int, notification_time.split(':'))
    target_minutes = hour * 60 + minute
    current_minutes = datetime.now().hour * 60 + datetime.now().minute

    return abs(current_minutes - target_minutes) <= 120  # ±2시간
```

### 전체 플로우

```
[15분마다 실행]
     │
     ▼
┌──────────────────────────────────────┐
│ 1. CLIENT 제외한 활성 사용자 조회     │
└──────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────┐
│ 2. 각 사용자별로:                     │
│    - 생성한 캠페인의 posts 조회       │
│    - due_date 있는 것만 필터링        │
└──────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────┐
│ 3. 각 post별로:                       │
│    ├─ due_date 파싱 (date_utils)     │
│    ├─ 알림 조건 체크:                │
│    │  ├─ 오늘 이미 전송했는지         │
│    │  ├─ 알림 시간대인지 (±2시간)    │
│    │  └─ 마감일 범위 내인지           │
│    └─ 조건 만족 시 전송              │
└──────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────┐
│ 4. 텔레그램 메시지 전송              │
│    - telegram_service.send_...()     │
└──────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────┐
│ 5. 로그 저장                         │
│    - TelegramNotificationLog 생성    │
│    - is_sent, error_message 기록     │
└──────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────┐
│ 6. last_notification_at 업데이트     │
└──────────────────────────────────────┘
```

---

## 날짜 처리 로직

**파일**: `app/utils/date_utils.py`

### 1. `parse_due_datetime(due_date_str, default_time, user_timezone)`

**목적**: due_date 문자열을 정확한 datetime으로 변환

**지원 형식**:
1. `"2025-09-25"` → `datetime(2025, 9, 25, 18, 0)` (기본 18:00)
2. `"2025-09-25 15:30"` → `datetime(2025, 9, 25, 15, 30)`
3. `"2025-09-25 15:30:00"` → `datetime(2025, 9, 25, 15, 30, 0)`
4. `"2025-09-25T15:30:00"` (ISO) → `datetime(2025, 9, 25, 15, 30, 0)`
5. `"2025-09-25T15:30:00Z"` (ISO + Z) → `datetime(2025, 9, 25, 15, 30, 0)`

**Parameters**:
- `due_date_str` (str): 파싱할 날짜 문자열
- `default_time` (str): 시간이 없을 때 기본 시간 (기본: "18:00")
- `user_timezone` (str, optional): 사용자 시간대 (향후 확장용)

**Returns**: `datetime` 객체 또는 `None` (파싱 실패 시)

---

### 2. `should_send_telegram_notification(due_datetime, days_before_setting, current_time, grace_period_hours)`

**목적**: 텔레그램 알림을 보내야 하는지 판단

**알림 조건**:
1. **마감 전**: `days_before_setting` 일 이내
2. **마감 후**: `grace_period_hours` 시간 이내 (유예 기간)

**예시**:
```python
# 사용자 설정: 2일 전 알림, 유예 12시간
days_before_setting = 2
grace_period_hours = 12.0

# 마감일: 2025-11-15 18:00
# 현재: 2025-11-13 10:00 → days_left = 2.33일 → ✅ 알림 (2일 이내)
# 현재: 2025-11-15 20:00 → days_left = -0.08일 → ✅ 알림 (마감 후 2시간, 유예 12시간 이내)
# 현재: 2025-11-16 10:00 → days_left = -0.67일 → ❌ 알림 안 함 (마감 후 16시간, 유예 초과)
```

**Parameters**:
- `due_datetime` (datetime): 마감 일시
- `days_before_setting` (int): 사용자 설정 (며칠 전 알림)
- `current_time` (datetime, optional): 현재 시간
- `grace_period_hours` (float): 마감 후 알림 유예시간 (기본: 12.0)

**Returns**: `(should_send: bool, days_left: float)`

---

### 3. `format_due_datetime_for_display(dt)`

**목적**: datetime을 사용자 친화적 형식으로 포맷팅

**예시**:
```python
dt = datetime(2025, 11, 15, 18, 0)
result = format_due_datetime_for_display(dt)
# result: "2025-11-15 18:00"
```

---

## 전체 코드

### 1. TelegramService 전체 코드

**파일**: `app/services/telegram_service.py`

```python
import asyncio
import httpx
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import os

logger = logging.getLogger(__name__)


class TelegramService:
    """텔레그램 봇 API 서비스"""

    def __init__(self, bot_token: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        self.timeout = 30.0

    async def send_message(
        self,
        chat_id: str,
        message: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True
    ) -> Dict[str, Any]:
        """텔레그램 메시지 전송"""

        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.")

        url = f"{self.base_url}/sendMessage"

        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    result = response.json()
                    if result.get("ok"):
                        logger.info(f"텔레그램 메시지 전송 성공: chat_id={chat_id}")
                        return {
                            "success": True,
                            "message_id": result.get("result", {}).get("message_id"),
                            "data": result
                        }
                    else:
                        error_msg = result.get("description", "알 수 없는 오류")
                        logger.error(f"텔레그램 API 오류: {error_msg}")
                        return {
                            "success": False,
                            "error": error_msg,
                            "error_code": result.get("error_code")
                        }
                else:
                    logger.error(f"텔레그램 API HTTP 오류: {response.status_code}")
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}",
                        "error_code": response.status_code
                    }

        except httpx.TimeoutException:
            logger.error("텔레그램 API 타임아웃")
            return {
                "success": False,
                "error": "요청 타임아웃",
                "error_code": "TIMEOUT"
            }
        except Exception as e:
            logger.error(f"텔레그램 메시지 전송 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "UNKNOWN"
            }

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """채팅 정보 조회 (chat_id 유효성 검증용)"""

        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.")

        url = f"{self.base_url}/getChat"
        payload = {"chat_id": chat_id}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    result = response.json()
                    if result.get("ok"):
                        return {
                            "success": True,
                            "data": result.get("result", {})
                        }
                    else:
                        return {
                            "success": False,
                            "error": result.get("description", "알 수 없는 오류")
                        }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"텔레그램 채팅 정보 조회 실패: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def send_campaign_deadline_reminder(
        self,
        chat_id: str,
        user_name: str,
        post_title: str,
        due_date: str,
        days_before: int,
        work_type: str = None,
        product_name: str = None
    ) -> Dict[str, Any]:
        """캠페인 마감일 알림 메시지 전송"""

        # 마감일이 임박한 정도에 따른 이모지 선택
        if days_before <= 1:
            urgency_emoji = "🚨"
            urgency_text = "긴급"
        elif days_before <= 2:
            urgency_emoji = "⚠️"
            urgency_text = "중요"
        else:
            urgency_emoji = "📅"
            urgency_text = "알림"

        # 메시지 기본 구조
        message_parts = [
            f"{urgency_emoji} <b>{urgency_text} - 캠페인 마감일 알림</b>",
            "",
            f"안녕하세요, <b>{user_name}</b>님!",
            "",
            f"📝 <b>작업명:</b> {post_title}"
        ]

        # work_type이 있으면 추가
        if work_type:
            message_parts.append(f"📋 <b>상품종류:</b> {work_type}")

        # product_name이 있으면 추가
        if product_name:
            message_parts.append(f"🔗 <b>상품명:</b> {product_name}")

        # 마감일과 남은 시간
        message_parts.extend([
            f"📅 <b>마감일:</b> {due_date}",
            f"⏰ <b>남은 시간:</b> <b>{days_before}일</b>",
            "",
            "마감일이 다가오고 있습니다. 작업 진행 상황을 확인해 주세요!",
            "",
            "<i>BrandFlow 알림 시스템</i>"
        ])

        message = "\n".join(message_parts)

        return await self.send_message(chat_id, message)

    async def send_test_message(self, chat_id: str, user_name: str) -> Dict[str, Any]:
        """테스트 메시지 전송"""

        message = f"""
🤖 <b>텔레그램 알림 테스트</b>

안녕하세요, <b>{user_name}</b>님!

✅ 텔레그램 알림이 정상적으로 설정되었습니다.
📱 이제 캠페인 마감일 알림을 받으실 수 있습니다.

<b>알림 설정:</b>
• 마감일 2일 전 알림
• 매일 오전 9시 발송

설정을 변경하시려면 시스템 설정에서 수정해 주세요.

<i>BrandFlow 알림 시스템</i>
        """.strip()

        return await self.send_message(chat_id, message)


# 전역 텔레그램 서비스 인스턴스
telegram_service = TelegramService()


async def send_telegram_message(chat_id: str, message: str) -> Dict[str, Any]:
    """간편한 텔레그램 메시지 전송 함수"""
    return await telegram_service.send_message(chat_id, message)


async def validate_telegram_chat_id(chat_id: str) -> bool:
    """텔레그램 채팅 ID 유효성 검증"""
    try:
        result = await telegram_service.get_chat_info(chat_id)
        return result.get("success", False)
    except Exception:
        return False
```

---

### 2. TelegramScheduler 전체 코드

**파일**: `app/services/telegram_scheduler.py`

```python
import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import List, Tuple
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import and_, func, or_

from app.db.database import sync_engine
from app.models.user import User, UserRole
from app.models.post import Post
from app.models.campaign import Campaign
from app.models.user_telegram_setting import UserTelegramSetting, TelegramNotificationLog
from app.services.telegram_service import telegram_service
from app.utils.date_utils import parse_due_datetime, should_send_telegram_notification, format_due_datetime_for_display

logger = logging.getLogger(__name__)

# 데이터베이스 세션 팩토리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


class TelegramScheduler:
    """텔레그램 알림 스케줄러"""

    def __init__(self):
        self.running = False
        self.check_interval = 900  # 15분마다 체크

    async def start(self):
        """스케줄러 시작"""
        if self.running:
            logger.warning("텔레그램 스케줄러가 이미 실행 중입니다")
            return

        self.running = True
        logger.info("텔레그램 알림 스케줄러 시작")

        while self.running:
            try:
                await self.check_and_send_notifications()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"스케줄러 오류: {str(e)}")
                await asyncio.sleep(60)  # 오류 시 1분 후 재시도

    def stop(self):
        """스케줄러 중지"""
        self.running = False
        logger.info("텔레그램 알림 스케줄러 중지")

    async def check_and_send_notifications(self):
        """마감일 임박 알림 확인 및 전송"""
        db = SessionLocal()

        try:
            logger.info(f"[TELEGRAM] 마감일 임박 알림 확인 시작 - {datetime.utcnow()}")

            # 클라이언트 역할을 제외한 모든 사용자들의 활성화된 텔레그램 설정 조회
            telegram_users = db.query(UserTelegramSetting).join(User).filter(
                and_(
                    User.role != UserRole.CLIENT,
                    UserTelegramSetting.is_enabled == True,
                    User.is_active == True
                )
            ).all()

            if not telegram_users:
                logger.info("[TELEGRAM] 알림을 받을 사용자가 없습니다")
                return

            logger.info(f"[TELEGRAM] 알림 대상 사용자 수: {len(telegram_users)}")

            notifications_sent = 0

            for telegram_setting in telegram_users:
                user = telegram_setting.user

                # 해당 사용자가 담당하는 posts 조회
                user_posts = await self.get_user_posts_with_upcoming_deadlines(
                    db, user.id, telegram_setting.days_before_due
                )

                for post_info in user_posts:
                    post, campaign, days_left = post_info

                    # 이미 알림을 보낸 적이 있는지 확인
                    existing_log = db.query(TelegramNotificationLog).filter(
                        and_(
                            TelegramNotificationLog.user_id == user.id,
                            TelegramNotificationLog.post_id == post.id,
                            TelegramNotificationLog.notification_type == "due_date_reminder",
                            TelegramNotificationLog.is_sent == True,
                            func.date(TelegramNotificationLog.created_at) == func.date(datetime.utcnow())
                        )
                    ).first()

                    if existing_log:
                        logger.debug(f"이미 알림 전송됨: user_id={user.id}, post_id={post.id}")
                        continue

                    # 알림 시간 확인
                    current_time = datetime.now().strftime("%H:%M")
                    if not self.is_notification_time(telegram_setting.notification_time):
                        logger.debug(f"[TELEGRAM] 알림 시간이 아님 - 설정: {telegram_setting.notification_time}, 현재: {current_time}")
                        continue

                    logger.info(f"[TELEGRAM] 알림 시간 조건 만족 - 사용자: {user.name}")

                    # 텔레그램 알림 전송
                    await self.send_deadline_notification(
                        db, user, post, campaign, days_left, telegram_setting
                    )
                    notifications_sent += 1

            logger.info(f"[TELEGRAM] 마감일 임박 알림 {notifications_sent}개 전송 완료")

        except Exception as e:
            logger.error(f"알림 확인 중 오류: {str(e)}")
        finally:
            db.close()

    async def get_user_posts_with_upcoming_deadlines(
        self, db: Session, user_id: int, days_before: int
    ) -> List[Tuple[Post, Campaign, float]]:
        """사용자의 마감일 임박 posts 조회"""

        try:
            now = datetime.now()
            logger.info(f"[TELEGRAM] 마감일 체크 기준 시간: {now}")

            # 사용자가 생성한 캠페인의 posts 조회
            posts_with_deadlines = db.query(Post, Campaign).join(Campaign).filter(
                and_(
                    Campaign.creator_id == user_id,
                    Post.due_date.isnot(None),
                    Post.due_date != '',
                    Post.is_active == True
                )
            ).all()

            logger.info(f"[TELEGRAM] 사용자 {user_id}의 마감일 있는 posts: {len(posts_with_deadlines)}개")

            upcoming_posts = []

            for post, campaign in posts_with_deadlines:
                try:
                    due_datetime = parse_due_datetime(post.due_date, default_time="18:00")

                    if not due_datetime:
                        logger.warning(f"[TELEGRAM] 날짜 파싱 실패: post_id={post.id}")
                        continue

                    should_send, days_left = should_send_telegram_notification(
                        due_datetime=due_datetime,
                        days_before_setting=days_before,
                        current_time=now,
                        grace_period_hours=12.0
                    )

                    if should_send:
                        upcoming_posts.append((post, campaign, days_left))
                        logger.info(f"[TELEGRAM] 알림 대상: Post {post.id} - {days_left:.1f}일 후 마감")

                except Exception as e:
                    logger.error(f"[TELEGRAM] Post {post.id} 처리 중 오류: {str(e)}")
                    continue

            return upcoming_posts

        except Exception as e:
            logger.error(f"마감일 임박 posts 조회 오류: {str(e)}")
            return []

    async def send_deadline_notification(
        self,
        db: Session,
        user: User,
        post: Post,
        campaign: Campaign,
        days_left: float,
        telegram_setting: UserTelegramSetting
    ):
        """마감일 알림 전송"""

        try:
            due_datetime = parse_due_datetime(post.due_date, default_time="18:00")
            due_info = format_due_datetime_for_display(due_datetime) if due_datetime else f"{post.due_date} 18:00"

            result = await telegram_service.send_campaign_deadline_reminder(
                chat_id=telegram_setting.telegram_chat_id,
                user_name=user.name,
                post_title=post.title,
                due_date=due_info,
                days_before=telegram_setting.days_before_due,
                work_type=post.work_type,
                product_name=post.product_name
            )

            # 로그 저장
            log = TelegramNotificationLog(
                user_id=user.id,
                post_id=post.id,
                campaign_id=campaign.id,
                notification_type="due_date_reminder",
                message_content=f"마감일 {telegram_setting.days_before_due}일 전 알림: {post.title}",
                telegram_chat_id=telegram_setting.telegram_chat_id,
                is_sent=result.get("success", False),
                sent_at=datetime.utcnow() if result.get("success") else None,
                error_message=result.get("error") if not result.get("success") else None,
                telegram_message_id=str(result.get("message_id", "")) if result.get("success") else None
            )

            db.add(log)
            db.commit()

            if result.get("success"):
                logger.info(f"마감일 알림 전송 성공: user={user.name}, post={post.title}")
                telegram_setting.last_notification_at = datetime.utcnow()
                db.commit()
            else:
                logger.error(f"마감일 알림 전송 실패: user={user.name}, error={result.get('error')}")

        except Exception as e:
            logger.error(f"마감일 알림 전송 중 오류: {str(e)}")

    def is_notification_time(self, notification_time: str) -> bool:
        """현재 시간이 알림 시간인지 확인 (±2시간)"""
        try:
            hour, minute = map(int, notification_time.split(':'))
            target_minutes = hour * 60 + minute
            current_minutes = datetime.now().hour * 60 + datetime.now().minute

            return abs(current_minutes - target_minutes) <= 120

        except Exception as e:
            logger.error(f"알림 시간 확인 오류: {str(e)}")
            return False


# 전역 스케줄러 인스턴스
telegram_scheduler = TelegramScheduler()


async def start_telegram_scheduler():
    """텔레그램 스케줄러 시작"""
    await telegram_scheduler.start()


def stop_telegram_scheduler():
    """텔레그램 스케줄러 중지"""
    telegram_scheduler.stop()
```

---

## 환경 변수 설정

**필수 환경 변수**:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

**설정 방법**:
1. Railway Dashboard → Environment Variables
2. `.env` 파일에 추가 (로컬 개발용)

---

## 텔레그램 봇 설정 방법

### 1. BotFather로 봇 생성
1. 텔레그램에서 `@BotFather` 검색
2. `/newbot` 명령어 입력
3. 봇 이름 입력 (예: BrandFlow Notification Bot)
4. 봇 사용자명 입력 (예: brandflow_notification_bot)
5. **Bot Token 복사** → 환경 변수에 설정

### 2. Chat ID 확인
1. 생성한 봇과 대화 시작 (`/start`)
2. 메시지 전송 (아무 메시지나)
3. 브라우저에서 접속:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
4. JSON에서 `chat.id` 값 확인 (예: `123456789`)

### 3. 시스템에 설정 등록
- API: `POST /api/telegram-settings/my-setting`
- Body:
  ```json
  {
    "telegram_chat_id": "123456789",
    "is_enabled": true,
    "days_before_due": 2,
    "notification_time": "09:00"
  }
  ```

---

## 테스트 방법

### 1. 테스트 메시지 발송
```bash
POST /api/telegram-settings/test
{
  "message": "테스트 메시지입니다."
}
```

### 2. 관리자 테스트 (마감일 알림 강제 실행)
```bash
POST /api/telegram-settings/test-deadline-notifications?force_all=true
```

### 3. 로그 확인
```bash
GET /api/telegram-settings/logs?limit=20
```

---

## 트러블슈팅

### 문제 1: 알림이 전송되지 않음

**체크리스트**:
1. `TELEGRAM_BOT_TOKEN` 환경 변수 설정 확인
2. `is_enabled = true` 확인
3. `User.is_active = true` 확인
4. 현재 시간이 알림 시간대인지 확인 (±2시간)
5. 오늘 이미 알림을 보냈는지 확인 (중복 방지)
6. 마감일이 `days_before_due` 범위 내인지 확인

### 문제 2: "Invalid chat_id" 오류

**해결**:
- Chat ID 확인 방법대로 정확한 ID 입력
- 봇과 대화를 먼저 시작해야 함 (`/start`)

### 문제 3: 스케줄러가 시작되지 않음

**해결**:
- `app/main.py`에 스케줄러 시작 코드 확인:
  ```python
  @app.on_event("startup")
  async def startup_event():
      asyncio.create_task(start_telegram_scheduler())
  ```

---

## 향후 개선 사항

1. **시간대 지원**: 사용자별 타임존 설정
2. **알림 빈도 설정**: 매일/주간/월간 등
3. **알림 유형 확장**: 캠페인 승인, 결제 완료 등
4. **Webhook 지원**: Polling 대신 Webhook 방식
5. **메시지 템플릿**: 사용자 정의 메시지 템플릿
6. **그룹 채팅 지원**: 팀 단위 알림

---

**문서 작성일**: 2025-10-30
**버전**: 1.0
**작성자**: Claude Code
