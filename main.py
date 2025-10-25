# FastAPI 메인 엔트리포인트 - Railway 배포용
import os
import logging
from app.main import app

# 로깅 설정 - Railway에서 로그가 보이도록 강제 설정
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))  # Railway 포트 환경변수
    print(f"Starting BrandFlow server on port: {port}")
    print(f"Environment: {'Railway' if os.environ.get('PORT') else 'Local'}")

    # uvicorn 로깅 레벨 설정
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="warning"  # WARNING 이상 로그 출력
    )