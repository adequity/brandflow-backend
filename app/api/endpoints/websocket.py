"""
WebSocket 엔드포인트
실시간 알림을 위한 WebSocket 연결 관리
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from typing import Optional
import jwt
import logging

from app.core.websocket import manager
from app.core.config import settings
from app.models.user import User
from app.db.database import get_async_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)

async def get_user_from_token(token: str, db: AsyncSession) -> Optional[User]:
    """JWT 토큰에서 사용자 정보 추출"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            return None
        
        # 사용자 조회
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        return user
        
    except jwt.InvalidTokenError:
        return None

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = None
):
    """
    WebSocket 연결 엔드포인트
    
    연결 URL: ws://localhost:8000/api/websocket/ws?token=JWT_TOKEN
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
        return
    
    # 데이터베이스 세션 생성
    from app.db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        # 토큰으로 사용자 인증
        user = await get_user_from_token(token, db)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return
        
        # WebSocket 연결 설정
        await manager.connect(websocket, user.id, user.role)
        
        try:
            # 연결 유지 및 메시지 수신 대기
            while True:
                # 클라이언트로부터 메시지 수신 (ping/pong 등)
                data = await websocket.receive_text()
                
                # 단순한 ping/pong 구현
                if data == "ping":
                    await manager.send_personal_message({
                        "type": "pong",
                        "message": "pong"
                    }, websocket)
                    
        except WebSocketDisconnect:
            manager.disconnect(websocket)
            logger.info(f"WebSocket disconnected for user {user.id}")
        except Exception as e:
            logger.error(f"WebSocket error for user {user.id}: {e}")
            manager.disconnect(websocket)

@router.get("/connections/stats")
async def get_connection_stats():
    """현재 WebSocket 연결 통계 조회 (관리자용)"""
    return manager.get_connection_stats()

@router.post("/test/broadcast")
async def test_broadcast(message: dict):
    """테스트용 브로드캐스트 메시지 전송 (개발용)"""
    await manager.broadcast({
        "type": "test",
        "title": "테스트 알림",
        "message": message.get("message", "테스트 메시지입니다."),
        "timestamp": "now"
    })
    return {"status": "sent"}

@router.post("/test/user/{user_id}")
async def test_user_message(user_id: int, message: dict):
    """테스트용 특정 사용자 메시지 전송 (개발용)"""
    await manager.send_to_user(user_id, {
        "type": "test",
        "title": "개인 테스트 알림",
        "message": message.get("message", "개인 테스트 메시지입니다."),
        "timestamp": "now"
    })
    return {"status": "sent", "user_id": user_id}

@router.post("/test/role/{role}")
async def test_role_message(role: str, message: dict):
    """테스트용 역할별 메시지 전송 (개발용)"""
    await manager.send_to_role(role, {
        "type": "test",
        "title": f"{role.upper()} 알림",
        "message": message.get("message", f"{role} 사용자를 위한 테스트 메시지입니다."),
        "timestamp": "now"
    })
    return {"status": "sent", "role": role}