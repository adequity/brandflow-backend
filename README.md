# BrandFlow FastAPI Backend

BrandFlow 캠페인 관리 시스템의 FastAPI 기반 백엔드 서버입니다.

## 🚀 기술 스택

- **FastAPI** - 현대적인 웹 프레임워크
- **PostgreSQL** - 안정적인 관계형 데이터베이스
- **SQLAlchemy** - ORM 및 데이터베이스 관리
- **Alembic** - 데이터베이스 마이그레이션
- **JWT** - 사용자 인증 및 권한 관리
- **Redis** - 캐싱 및 세션 관리
- **Docker** - 컨테이너화

## 📁 프로젝트 구조

```
brandflow-fastapi/
├── app/
│   ├── api/                # API 라우터와 엔드포인트
│   │   ├── endpoints/      # 각 도메인별 엔드포인트
│   │   ├── deps.py         # 의존성 주입
│   │   └── router.py       # 메인 라우터
│   ├── core/               # 핵심 설정 및 보안
│   │   ├── config.py       # 환경 설정
│   │   └── security.py     # JWT 및 패스워드 처리
│   ├── db/                 # 데이터베이스 설정
│   │   ├── database.py     # DB 연결 및 세션
│   │   └── init_data.py    # 초기 데이터
│   ├── models/             # SQLAlchemy 모델
│   ├── schemas/            # Pydantic 스키마
│   ├── services/           # 비즈니스 로직
│   └── main.py             # FastAPI 애플리케이션
├── alembic/                # 데이터베이스 마이그레이션
├── docker-compose.yml      # 개발용 DB 서비스
└── requirements.txt        # Python 의존성
```

## ⚙️ 설정 방법

### 1. 환경 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집 (데이터베이스 URL, 시크릿 키 등)
```

### 2. 데이터베이스 시작

#### PostgreSQL 사용 (권장)

```bash
# Docker Compose로 PostgreSQL과 Redis 시작
docker-compose up -d postgres

# 또는 PostgreSQL 시작 도우미 스크립트 사용
python start_postgresql.py
```

#### Railway PostgreSQL 사용 (현재 설정)

```bash
# Railway PostgreSQL이 이미 설정되어 있습니다
# .env 파일에 Railway PostgreSQL URL이 구성됨
DATABASE_URL=postgresql+asyncpg://postgres:kAPUkGlWqoHwxIvtWaeukQuwcrZpSzuu@junction.proxy.rlwy.net:21652/railway

# FastAPI 서버 시작
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Python 환경 설정

```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화 (Windows)
venv\\Scripts\\activate

# 의존성 설치
pip install -r requirements.txt
```

### 4. 데이터베이스 마이그레이션

```bash
# 초기 마이그레이션 생성
alembic revision --autogenerate -m "Initial migration"

# 마이그레이션 적용
alembic upgrade head
```

### 5. 서버 시작

```bash
# 개발 서버 시작
python app/main.py

# 또는 uvicorn 직접 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📚 API 문서

서버가 실행되면 다음 URL에서 API 문서를 확인할 수 있습니다:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔐 기본 계정

시스템 초기 실행 시 기본 슈퍼 어드민 계정이 생성됩니다:

- **이메일**: admin@test.com
- **비밀번호**: admin123

## 🛡️ 보안 기능

- JWT 토큰 기반 인증
- 비밀번호 bcrypt 해싱
- 역할 기반 접근 제어 (RBAC)
- CORS 정책 설정
- 입력 값 검증 및 살균

## 🚀 배포

### Docker 배포

```bash
# Dockerfile 생성 후
docker build -t brandflow-api .
docker run -p 8000:8000 brandflow-api
```

### 환경변수 설정

프로덕션 환경에서는 다음 환경변수들을 적절히 설정해야 합니다:

- `DATABASE_URL`: PostgreSQL 연결 문자열
- `SECRET_KEY`: JWT 암호화 키 (충분히 복잡하게!)
- `REDIS_URL`: Redis 연결 문자열
- `ALLOWED_ORIGINS`: CORS 허용 도메인 목록

## 🧪 테스트

```bash
# 테스트 실행
pytest

# 커버리지와 함께
pytest --cov=app
```

## 📈 모니터링

- 헬스체크: `GET /health`
- 메트릭: `GET /metrics` (구현 예정)
- 로깅: 구조화된 JSON 로그

## 🔧 개발 도구

- **Black**: 코드 포맷팅
- **Flake8**: 린팅
- **mypy**: 타입 체킹
- **pytest**: 테스트 프레임워크

## 🤝 기여하기

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Add tests
5. Submit a pull request

## 📄 라이선스

MIT License# Force deployment 2025년 09월  5일 금 오후  8:13:25
# Force redeploy trigger
# Force redeploy - 2025년 09월 30일 화 오전  4:45:10
# Deployment trigger 2025년 09월 30일 화 오후  5:29:13
# Railway deployment trigger
# Force redeploy
# Force rebuild
