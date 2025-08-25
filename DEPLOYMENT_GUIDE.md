# BrandFlow 프로덕션 배포 가이드

## 📋 목차
1. [사전 요구사항](#사전-요구사항)
2. [환경 설정](#환경-설정)
3. [Docker 배포](#docker-배포)
4. [SSL 인증서 설정](#ssl-인증서-설정)
5. [모니터링 및 로깅](#모니터링-및-로깅)
6. [백업 및 복구](#백업-및-복구)
7. [문제 해결](#문제-해결)

## 🔧 사전 요구사항

### 시스템 요구사항
- **OS**: Ubuntu 20.04+ 또는 CentOS 8+
- **CPU**: 2코어 이상
- **RAM**: 4GB 이상 (권장: 8GB)
- **Storage**: 50GB 이상 (권장: 100GB)
- **Network**: 인터넷 연결 및 도메인

### 필수 소프트웨어
```bash
# Docker 및 Docker Compose 설치
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Git 설치
sudo apt update
sudo apt install git -y
```

## ⚙️ 환경 설정

### 1. 저장소 클론
```bash
git clone <your-repository-url>
cd brandflow-fastapi
```

### 2. 환경 변수 설정
```bash
# 환경 변수 파일 생성
cp .env.example .env

# 환경 변수 편집 (중요: 실제 값으로 변경)
nano .env
```

### 필수 변경 사항
```bash
# 보안 키 생성 (Python으로)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# .env 파일에서 변경해야 할 주요 항목:
ENVIRONMENT=production
SECRET_KEY=<생성된-보안-키>
DATABASE_URL=postgresql://brandflow_user:<strong-password>@postgres:5432/brandflow
POSTGRES_PASSWORD=<strong-database-password>
REDIS_PASSWORD=<strong-redis-password>
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### 3. SSL 인증서 준비
#### Let's Encrypt 사용 (무료)
```bash
# Certbot 설치
sudo apt install certbot python3-certbot-nginx -y

# 인증서 발급 (도메인 변경 필요)
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# 인증서 파일을 SSL 디렉토리로 복사
sudo mkdir -p ./ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ./ssl/brandflow.crt
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ./ssl/brandflow.key
sudo chown $(whoami):$(whoami) ./ssl/*
```

#### 자체 서명 인증서 (개발/테스트용)
```bash
mkdir -p ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout ssl/brandflow.key \
    -out ssl/brandflow.crt \
    -subj "/C=KR/ST=Seoul/L=Seoul/O=BrandFlow/CN=localhost"
```

## 🐳 Docker 배포

### 1. 빌드 및 실행
```bash
# 백그라운드에서 모든 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 특정 서비스 로그 확인
docker-compose logs -f brandflow-backend
```

### 2. 데이터베이스 초기화
```bash
# 데이터베이스 마이그레이션
docker-compose exec brandflow-backend alembic upgrade head

# 초기 데이터 생성 (선택사항)
docker-compose exec brandflow-backend python -c "
from app.db.database import AsyncSessionLocal
from app.db.init_data import init_database_data
import asyncio

async def main():
    async with AsyncSessionLocal() as session:
        await init_database_data(session)
        print('Initial data created')

asyncio.run(main())
"
```

### 3. 서비스 상태 확인
```bash
# 컨테이너 상태 확인
docker-compose ps

# 헬스체크 확인
curl -k https://localhost/health

# API 문서 확인
curl -k https://localhost/docs
```

## 🔐 SSL 인증서 설정

### 인증서 자동 갱신 설정
```bash
# crontab 편집
sudo crontab -e

# 다음 줄 추가 (매월 1일 새벽 3시에 갱신)
0 3 1 * * /usr/bin/certbot renew --quiet && docker-compose restart nginx
```

### Nginx 설정 커스터마이징
```bash
# Nginx 설정 파일 편집
nano nginx/nginx.conf

# 도메인명 변경
sed -i 's/localhost/yourdomain.com/g' nginx/nginx.conf

# 설정 적용
docker-compose restart nginx
```

## 📊 모니터링 및 로깅

### 1. 로그 관리
```bash
# 애플리케이션 로그 확인
docker-compose logs --tail=100 brandflow-backend

# 실시간 로그 모니터링
docker-compose logs -f brandflow-backend

# 로그 로테이션 설정 (logrotate)
sudo nano /etc/logrotate.d/brandflow
```

### 2. 시스템 모니터링
```bash
# 리소스 사용량 확인
docker stats

# 디스크 사용량 확인
df -h

# 메모리 사용량 확인
free -h
```

### 3. 애플리케이션 모니터링
- **성능 대시보드**: `https://yourdomain.com/api/performance-dashboard/metrics`
- **보안 대시보드**: `https://yourdomain.com/api/security-dashboard/summary`
- **헬스체크**: `https://yourdomain.com/health`

## 💾 백업 및 복구

### 1. 데이터베이스 백업
```bash
# 백업 디렉토리 생성
mkdir -p backups

# PostgreSQL 백업
docker-compose exec postgres pg_dump -U brandflow_user brandflow > backups/brandflow_$(date +%Y%m%d_%H%M%S).sql

# 자동 백업 스크립트 생성
cat > backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="./backups"
mkdir -p $BACKUP_DIR
docker-compose exec -T postgres pg_dump -U brandflow_user brandflow > $BACKUP_DIR/brandflow_$(date +%Y%m%d_%H%M%S).sql
# 30일 이상된 백업 파일 삭제
find $BACKUP_DIR -name "brandflow_*.sql" -mtime +30 -delete
EOF

chmod +x backup.sh

# crontab에 추가 (매일 새벽 2시)
(crontab -l 2>/dev/null; echo "0 2 * * * /path/to/your/brandflow-fastapi/backup.sh") | crontab -
```

### 2. 데이터베이스 복구
```bash
# PostgreSQL 복구
docker-compose exec -T postgres psql -U brandflow_user -d brandflow < backups/brandflow_20240125_020000.sql
```

### 3. 볼륨 백업
```bash
# Docker 볼륨 백업
docker run --rm -v brandflow-fastapi_postgres_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/postgres_data_$(date +%Y%m%d).tar.gz -C /data .
docker run --rm -v brandflow-fastapi_redis_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/redis_data_$(date +%Y%m%d).tar.gz -C /data .
```

## 🔄 업데이트 및 배포

### 1. 무중단 배포
```bash
# 새 버전 빌드
docker-compose build brandflow-backend

# 롤링 업데이트
docker-compose up -d --no-deps brandflow-backend

# 헬스체크 확인
curl -f https://yourdomain.com/health || docker-compose rollback
```

### 2. 롤백 절차
```bash
# 이전 이미지로 롤백
docker-compose down
docker-compose up -d

# 또는 특정 버전으로 롤백
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 🛠️ 문제 해결

### 일반적인 문제들

#### 1. 컨테이너가 시작되지 않는 경우
```bash
# 로그 확인
docker-compose logs brandflow-backend

# 개별 컨테이너 디버깅
docker run -it --rm brandflow-fastapi_brandflow-backend /bin/bash
```

#### 2. 데이터베이스 연결 오류
```bash
# PostgreSQL 연결 테스트
docker-compose exec postgres psql -U brandflow_user -d brandflow -c "SELECT version();"

# 네트워크 확인
docker network ls
docker network inspect brandflow-fastapi_brandflow-network
```

#### 3. SSL 인증서 문제
```bash
# 인증서 유효성 확인
openssl x509 -in ssl/brandflow.crt -text -noout

# 인증서 만료일 확인
openssl x509 -in ssl/brandflow.crt -noout -dates
```

#### 4. 성능 문제
```bash
# 리소스 사용량 모니터링
docker stats --no-stream

# 느린 쿼리 확인
docker-compose exec postgres psql -U brandflow_user -d brandflow -c "
SELECT query, mean_exec_time, calls 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 10;"
```

### 로그 위치
- **애플리케이션 로그**: `./logs/app.log`
- **Nginx 로그**: `./logs/nginx/`
- **Docker 로그**: `docker-compose logs <service>`

### 중요한 포트들
- **80**: HTTP (HTTPS로 리다이렉트)
- **443**: HTTPS (Nginx)
- **8000**: FastAPI (내부 전용)
- **5432**: PostgreSQL (내부 전용)
- **6379**: Redis (내부 전용)

## 📞 지원 및 연락처

문제가 발생하거나 추가 지원이 필요한 경우:
1. 로그 파일 확인
2. GitHub Issues 등록
3. 문서 재검토

---

**보안 주의사항**:
- `.env` 파일을 절대 공개 저장소에 커밋하지 마세요
- 정기적으로 보안 업데이트를 적용하세요
- 백업 파일의 접근 권한을 적절히 설정하세요
- SSL 인증서 만료일을 주기적으로 확인하세요