# BrandFlow FastAPI 배포 가이드

이 문서는 BrandFlow FastAPI 백엔드를 다양한 플랫폼에 배포하는 방법을 설명합니다.

## 📋 목차

1. [배포 준비](#배포-준비)
2. [Railway 배포](#railway-배포)
3. [Docker 배포](#docker-배포)
4. [GitHub Actions CI/CD](#github-actions-cicd)
5. [모니터링 설정](#모니터링-설정)
6. [트러블슈팅](#트러블슈팅)

## 🚀 배포 준비

### 환경 변수 설정

배포 전 다음 환경 변수들을 설정해야 합니다:

```bash
# 필수 환경 변수
DATABASE_URL=sqlite:///./data/brandflow.db  # 또는 PostgreSQL URL
SECRET_KEY=your-super-secret-key-change-this
JWT_SECRET_KEY=your-jwt-secret-key

# 선택사항
ACCESS_TOKEN_EXPIRE_MINUTES=30
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
ENVIRONMENT=production
DEBUG=false
```

### 의존성 확인

```bash
pip install -r requirements.txt
python -c "import app.main; print('✅ 코드 import 성공')"
```

## 🚂 Railway 배포

### 1. Railway CLI 설치

```bash
# npm을 통한 설치
npm install -g @railway/cli

# 또는 curl을 통한 설치
curl -fsSL https://railway.app/install.sh | sh
```

### 2. Railway 로그인

```bash
railway login
```

### 3. 프로젝트 초기화 및 배포

```bash
# 새 프로젝트 생성
railway init

# 환경 변수 설정
railway variables set SECRET_KEY=your-secret-key
railway variables set JWT_SECRET_KEY=your-jwt-key
railway variables set DATABASE_URL=sqlite:///./data/brandflow.db

# 배포 실행
railway up
```

### 4. 자동 배포 스크립트 사용

```bash
chmod +x deploy.sh
./deploy.sh railway
```

### 5. 도메인 설정 (선택사항)

Railway 대시보드에서 커스텀 도메인을 설정할 수 있습니다.

## 🐳 Docker 배포

### 1. Docker 이미지 빌드

```bash
docker build -t brandflow-api .
```

### 2. 단일 컨테이너 실행

```bash
docker run -d \
  -p 8000:8000 \
  -e SECRET_KEY=your-secret-key \
  -e JWT_SECRET_KEY=your-jwt-key \
  -v ./data:/app/data \
  --name brandflow-api \
  brandflow-api
```

### 3. Docker Compose 사용 (권장)

```bash
# 환경 변수 파일 생성
cp .env.example .env
# .env 파일 편집

# 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 서비스 중지
docker-compose down
```

### 4. 프로덕션 환경 설정

```bash
# 프로덕션용 compose 파일 사용
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 🔄 GitHub Actions CI/CD

### 1. GitHub Secrets 설정

Repository Settings → Secrets and variables → Actions에서 다음을 설정:

```
RAILWAY_TOKEN=your-railway-token
RAILWAY_SERVICE_NAME=your-service-name
RAILWAY_APP_URL=https://your-app.railway.app
```

### 2. 워크플로우 파일

`.github/workflows/deploy.yml` 파일이 자동으로 다음을 수행합니다:

- 코드 변경 시 자동 테스트
- main 브랜치 푸시 시 Railway 자동 배포
- 배포 후 헬스 체크 및 모니터링 검증

### 3. 수동 배포 트리거

GitHub Repository → Actions → Deploy to Railway → Run workflow

## 📊 모니터링 설정

### 1. 헬스 체크 엔드포인트

```bash
# 기본 헬스 체크
curl https://your-app.railway.app/health

# 모니터링 시스템 상태
curl https://your-app.railway.app/api/monitoring/health
```

### 2. 시스템 모니터링 (관리자만)

```bash
# 시스템 통계
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-app.railway.app/api/monitoring/system

# 대시보드 데이터
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-app.railway.app/api/monitoring/dashboard
```

### 3. 로그 모니터링

- **Railway**: Railway 대시보드에서 실시간 로그 확인
- **Docker**: `docker-compose logs -f brandflow-backend`
- **애플리케이션 로그**: `/app/logs` 디렉토리

## 🔧 트러블슈팅

### 일반적인 문제들

#### 1. 모듈 import 오류

```bash
# 해결방법
export PYTHONPATH=/app:$PYTHONPATH
```

#### 2. 데이터베이스 연결 실패

```bash
# SQLite 권한 확인
ls -la data/
chmod 664 data/brandflow.db

# PostgreSQL 연결 확인
pg_isready -h localhost -p 5432 -U username
```

#### 3. Railway 배포 실패

```bash
# Railway 상태 확인
railway status

# 로그 확인
railway logs

# 환경 변수 확인
railway variables
```

#### 4. Docker 컨테이너 문제

```bash
# 컨테이너 상태 확인
docker ps -a

# 로그 확인
docker logs brandflow-api

# 컨테이너 내부 접속
docker exec -it brandflow-api /bin/bash
```

#### 5. 모니터링 시스템 오류

```bash
# 모니터링 미들웨어 상태 확인
curl https://your-app.railway.app/api/monitoring/health

# 서버 재시작
railway restart  # Railway
docker-compose restart brandflow-backend  # Docker
```

## 📈 성능 최적화

### 1. 데이터베이스 최적화

```sql
-- 인덱스 확인
PRAGMA index_list('users');

-- 성능 모니터링
SELECT * FROM sqlite_master WHERE type='index';
```

### 2. 캐싱 설정 (Redis)

```bash
# Redis 연결 확인
redis-cli ping

# 캐시 통계
redis-cli info stats
```

### 3. 리소스 모니터링

- **CPU/메모리**: Railway 대시보드 또는 `docker stats`
- **디스크**: `df -h /app/data`
- **네트워크**: 모니터링 API 엔드포인트 사용

## 🔐 보안 체크리스트

- [ ] 환경 변수로 모든 시크릿 관리
- [ ] HTTPS 강제 사용
- [ ] CORS 적절히 설정
- [ ] 정기적인 의존성 업데이트
- [ ] 로그에서 민감한 정보 제거
- [ ] 관리자 권한 API 보호

## 📞 지원

배포 중 문제가 발생하면:

1. 이 문서의 트러블슈팅 섹션 확인
2. 로그 파일 검토
3. GitHub Issues에 문제 보고

---

**마지막 업데이트**: 2025-08-26
**버전**: v2.0.0