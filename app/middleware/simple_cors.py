"""
간단한 CORS 미들웨어 - Railway 배포용
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class SimpleCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # OPTIONS 요청 처리
        if request.method == "OPTIONS":
            response = Response()
        else:
            response = await call_next(request)
        
        # CORS 헤더 추가
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Expose-Headers"] = "X-Total-Count, X-Page-Count"
        response.headers["Access-Control-Max-Age"] = "86400"
        
        return response
