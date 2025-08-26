# BrandFlow FastAPI Backend Dockerfile - Multi-platform Optimized
FROM python:3.11-slim

# 환경 변수 설정
ENV PYTHONPATH=/app
ENV ENVIRONMENT=production
ENV PYTHONUNBUFFERED=1

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# requirements.txt 복사 및 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 애플리케이션 소스 복사
COPY . .

# 데이터 디렉토리 생성
RUN mkdir -p /app/data /app/logs /app/uploads

# Railway 테스트용 권한 단순화 (root 사용)
# RUN adduser --system --group appuser && chown -R appuser:appuser /app
# USER appuser

# 포트 설정 (Railway는 8000, Render는 10000)
EXPOSE 8000
EXPOSE 10000

# Railway handles healthcheck internally via railway.json
# HEALTHCHECK removed to avoid conflicts

# Railway 테스트용 단순 시작
CMD ["python", "simple_main.py"]