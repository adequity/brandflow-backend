# FastAPI 메인 엔트리포인트 - Railway 배포용
from app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)