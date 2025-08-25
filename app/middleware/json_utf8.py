"""
UTF-8 JSON 처리를 위한 미들웨어
"""
import json
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Callable


class UTF8JSONMiddleware(BaseHTTPMiddleware):
    """UTF-8 JSON 처리를 위한 미들웨어"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Content-Type이 application/json인 경우 UTF-8 인코딩 보장
        if (
            hasattr(request, "headers") and 
            request.headers.get("content-type", "").startswith("application/json")
        ):
            # Request body를 UTF-8로 읽어서 재설정
            try:
                body = await request.body()
                if body:
                    # UTF-8로 디코딩 후 다시 인코딩하여 유효성 확인
                    decoded_body = body.decode('utf-8')
                    # JSON 유효성 검사
                    json.loads(decoded_body)
                    # 요청 객체에 올바른 UTF-8 body 설정
                    request._body = decoded_body.encode('utf-8')
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"Invalid JSON or encoding: {str(e)}"}
                )
        
        response = await call_next(request)
        
        # Response가 JSON인 경우 UTF-8 Content-Type 헤더 설정
        if isinstance(response, JSONResponse):
            response.headers["content-type"] = "application/json; charset=utf-8"
        
        return response