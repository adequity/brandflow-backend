# FastAPI 메인 엔트리포인트 - Railway 배포용
import os
from app.main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)