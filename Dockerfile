# BrandFlow FastAPI Backend Dockerfile - Render Optimized
FROM python:3.11-slim

# 환경 변수 설정
ENV PYTHONPATH=/app
ENV ENVIRONMENT=production

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 설치 (최소한만)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt 복사 및 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 소스 복사
COPY . .

# 데이터 디렉토리 생성
RUN mkdir -p /app/data

# 포트 설정 (환경변수에서 가져오거나 기본값 8000)
EXPOSE $PORT

# 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:$PORT/health || exit 1

# 애플리케이션 시작 (Render의 PORT 환경변수 사용)
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT