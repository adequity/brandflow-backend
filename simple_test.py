from fastapi import FastAPI
import uvicorn

app = FastAPI(title="Simple Test")

@app.get("/")
async def root():
    return {"message": "Simple test working", "status": "ok"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("simple_test:app", host="0.0.0.0", port=8000)