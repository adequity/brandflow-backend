# BrandFlow FastAPI Backend Dockerfile
# 멀티스테이지 빌드로 이미지 크기 최적화

# Stage 1: 빌드 환경
FROM python:3.11-slim as builder

# 시스템 패키지 업데이트 및 필수 도구 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치를 위한 임시 디렉토리
WORKDIR /app

# requirements.txt 복사 및 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: 프로덕션 환경  
FROM python:3.11-slim

# 비루트 사용자 생성 (보안 강화)
RUN groupadd -r brandflow && useradd -r -g brandflow brandflow

# 시스템 패키지 업데이트 및 런타임 의존성 설치
RUN apt-get update && apt-get install -y \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Python 의존성 복사
COPY --from=builder /root/.local /home/brandflow/.local

# 애플리케이션 디렉토리 생성
WORKDIR /app

# 애플리케이션 소스 복사
COPY --chown=brandflow:brandflow . .

# 환경 변수 설정
ENV PATH=/home/brandflow/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV ENVIRONMENT=production
ENV DATABASE_URL=sqlite:///./brandflow.db

# 데이터베이스 및 로그 디렉토리 생성
RUN mkdir -p /app/data /app/logs \
    && chown -R brandflow:brandflow /app/data /app/logs

# 포트 노출
EXPOSE 8000

# 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# 비루트 사용자로 전환
USER brandflow

# 애플리케이션 시작
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]