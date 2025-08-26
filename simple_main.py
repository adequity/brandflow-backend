# Railway 테스트용 극단적으로 단순한 FastAPI
from fastapi import FastAPI
import os

app = FastAPI(title="BrandFlow Simple Test")

@app.get("/")
async def root():
    return {
        "message": "BrandFlow FastAPI v2.0.0 - Railway Test", 
        "status": "running",
        "port": os.getenv("PORT", "unknown")
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)