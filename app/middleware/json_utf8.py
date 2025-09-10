"""
UTF-8 JSON 처리를 위한 미들웨어 - 한글 처리 강화
"""
import json
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Callable

# UTF-8 처리 로깅
logger = logging.getLogger(__name__)


class UTF8JSONMiddleware(BaseHTTPMiddleware):
    """UTF-8 JSON 처리를 위한 미들웨어 - 한글 처리 강화"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Content-Type이 application/json인 경우 UTF-8 인코딩 보장
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            try:
                body = await request.body()
                if body:
                    # UTF-8로 디코딩
                    try:
                        decoded_body = body.decode('utf-8')
                    except UnicodeDecodeError as e:
                        logger.error(f"UTF-8 decoding failed: {e}")
                        return JSONResponse(
                            status_code=400,
                            content={"detail": f"UTF-8 디코딩 오류: 요청 데이터가 올바른 UTF-8 형식이 아닙니다. ({str(e)})"}
                        )
                    
                    # 한글 문자 확인 및 로깅
                    if any('\u3131' <= char <= '\uD79D' for char in decoded_body):
                        logger.info(f"SUCCESS 한글 문자 감지됨 - UTF-8 처리: {decoded_body[:100]}...")
                    
                    # JSON 유효성 검사
                    try:
                        parsed_json = json.loads(decoded_body)
                        logger.info(f"SUCCESS JSON 파싱 성공: {type(parsed_json)}")
                        
                        # 한글 필드 로깅
                        if isinstance(parsed_json, dict):
                            for key, value in parsed_json.items():
                                if isinstance(value, str) and any('\u3131' <= char <= '\uD79D' for char in value):
                                    logger.info(f"SUCCESS 한글 필드 확인: {key} = {value}")
                                    
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON parsing failed: {e}")
                        return JSONResponse(
                            status_code=400,
                            content={"detail": f"JSON 형식 오류: {str(e)}"}
                        )
                    
                    # 요청 객체에 올바른 UTF-8 body 설정
                    request._body = decoded_body.encode('utf-8')
                    
            except Exception as e:
                logger.error(f"UTF-8 middleware error: {e}")
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"요청 처리 중 오류가 발생했습니다: {str(e)}"}
                )
        
        # 다음 미들웨어/핸들러 호출
        response = await call_next(request)
        
        # Response가 JSON인 경우 UTF-8 Content-Type 헤더 설정
        if isinstance(response, JSONResponse):
            response.headers["content-type"] = "application/json; charset=utf-8"
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Expose-Headers"] = "X-Total-Count, X-Page-Count"
        
        return response