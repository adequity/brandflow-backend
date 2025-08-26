# Railway 웹 배포 단계별 가이드

## 🚂 Railway 웹 대시보드를 통한 배포

### 1단계: Railway 로그인
1. [Railway.app](https://railway.app)에 접속
2. GitHub 계정으로 로그인

### 2단계: 새 프로젝트 생성
1. "New Project" 클릭
2. "Deploy from GitHub repo" 선택
3. `adequity/brandflow-backend` 저장소 선택
4. Branch: `fastapi` 선택

### 3단계: 환경 변수 설정
Railway 프로젝트 설정에서 다음 환경 변수들을 추가:

```
DATABASE_URL=sqlite:///./data/brandflow.db
SECRET_KEY=your-super-secret-key-change-this-for-production
JWT_SECRET_KEY=your-jwt-secret-key-change-this-too
ACCESS_TOKEN_EXPIRE_MINUTES=30
ENVIRONMENT=production
DEBUG=false
CORS_ORIGINS=https://yourdomain.com
```

### 4단계: 배포 설정 확인
- `railway.json` 설정이 자동으로 감지됨
- Dockerfile 기반 빌드 확인
- 헬스체크 경로: `/health`

### 5단계: 배포 실행
- "Deploy" 버튼 클릭
- 빌드 로그 모니터링
- 배포 완료 대기

### 6단계: 배포 확인
배포가 완료되면 Railway가 제공하는 URL에서 다음을 확인:

1. **기본 헬스 체크**: `https://your-app.railway.app/health`
   ```json
   {"status":"healthy"}
   ```

2. **API 문서**: `https://your-app.railway.app/docs`
   - FastAPI 자동 생성 Swagger UI

3. **모니터링 헬스 체크**: `https://your-app.railway.app/api/monitoring/health`
   ```json
   {"status":"healthy","timestamp":"...","uptime":123.45}
   ```

## 🔧 Railway CLI를 통한 배포 (대안)

### CLI 로그인 방법:
```bash
# 터미널에서 실행
railway login

# 브라우저에서 인증 후 터미널로 돌아와서
railway link  # 기존 프로젝트에 연결
# 또는
railway init  # 새 프로젝트 생성

# 환경 변수 설정
railway variables set SECRET_KEY=your-secret-key
railway variables set JWT_SECRET_KEY=your-jwt-key
railway variables set DATABASE_URL=sqlite:///./data/brandflow.db

# 배포 실행
railway up
```

## 📊 배포 후 확인사항

### 1. 기본 API 테스트
```bash
# 헬스 체크
curl https://your-app.railway.app/health

# API 루트
curl https://your-app.railway.app/

# 모니터링 상태
curl https://your-app.railway.app/api/monitoring/health
```

### 2. 로그인 테스트
```bash
# 관리자 로그인 테스트
curl -X POST "https://your-app.railway.app/api/auth/login-json" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"BrandFlow2024!Admin"}'
```

### 3. 모니터링 시스템 확인
관리자 토큰으로 모니터링 API 접근:
```bash
# 시스템 통계 (관리자 토큰 필요)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-app.railway.app/api/monitoring/system

# 성능 대시보드
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-app.railway.app/api/monitoring/dashboard
```

## 🚨 트러블슈팅

### 배포 실패 시
1. Railway 프로젝트 로그 확인
2. Dockerfile 빌드 오류 확인
3. 환경 변수 설정 확인

### 데이터베이스 문제
- SQLite 파일이 자동으로 생성되는지 확인
- `/data` 디렉토리 권한 확인

### 모니터링 시스템 오류
- `/api/monitoring/health` 엔드포인트 접근 확인
- 관리자 권한 API는 토큰 필요

## 📈 성공 지표

✅ **배포 성공**: Railway 대시보드에서 "Running" 상태  
✅ **헬스 체크 통과**: `/health` 엔드포인트 200 응답  
✅ **API 작동**: `/docs`에서 Swagger UI 접근 가능  
✅ **모니터링 활성화**: 요청 로그가 Railway 로그에 표시  
✅ **인증 시스템 작동**: 로그인/로그아웃 API 정상 동작  

---

**현재 상태**: 코드가 GitHub에 푸시 완료, Railway 배포 준비 완료  
**다음 단계**: Railway 웹 대시보드에서 배포 진행