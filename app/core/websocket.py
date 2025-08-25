"""
WebSocket 연결 관리자
실시간 알림 및 이벤트 브로드캐스팅을 위한 WebSocket 관리
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set, Optional, Any
import json
import asyncio
import logging
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class NotificationType(str, Enum):
    """알림 타입 정의"""
    CAMPAIGN_UPDATE = "campaign_update"
    PURCHASE_REQUEST = "purchase_request"
    USER_ACTIVITY = "user_activity"
    SYSTEM_ALERT = "system_alert"
    PERFORMANCE_ALERT = "performance_alert"
    SECURITY_ALERT = "security_alert"

class ConnectionManager:
    """WebSocket 연결 관리자"""
    
    def __init__(self):
        # 사용자별 활성 연결 관리
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # 역할별 연결 관리 (관리자, 일반 사용자)
        self.connections_by_role: Dict[str, Set[WebSocket]] = {
            "admin": set(),
            "user": set()
        }
        # 연결별 사용자 정보
        self.connection_users: Dict[WebSocket, Dict[str, Any]] = {}
        
    async def connect(self, websocket: WebSocket, user_id: int, user_role: str = "user"):
        """새 WebSocket 연결 승인 및 등록"""
        await websocket.accept()
        
        # 사용자별 연결 목록에 추가
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        
        # 역할별 연결 목록에 추가
        if user_role in self.connections_by_role:
            self.connections_by_role[user_role].add(websocket)
        
        # 연결 메타데이터 저장
        self.connection_users[websocket] = {
            "user_id": user_id,
            "role": user_role,
            "connected_at": datetime.utcnow(),
            "last_activity": datetime.utcnow()
        }
        
        logger.info(f"User {user_id} ({user_role}) connected via WebSocket")
        
        # 연결 확인 메시지 전송
        await self.send_personal_message({
            "type": "connection_established",
            "message": "실시간 알림 연결이 설정되었습니다.",
            "timestamp": datetime.utcnow().isoformat()
        }, websocket)

    def disconnect(self, websocket: WebSocket):
        """WebSocket 연결 해제"""
        if websocket in self.connection_users:
            user_info = self.connection_users[websocket]
            user_id = user_info["user_id"]
            user_role = user_info["role"]
            
            # 사용자별 연결 목록에서 제거
            if user_id in self.active_connections:
                self.active_connections[user_id] = [
                    conn for conn in self.active_connections[user_id] 
                    if conn != websocket
                ]
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
            
            # 역할별 연결 목록에서 제거
            if user_role in self.connections_by_role:
                self.connections_by_role[user_role].discard(websocket)
            
            # 연결 메타데이터 제거
            del self.connection_users[websocket]
            
            logger.info(f"User {user_id} ({user_role}) disconnected from WebSocket")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """특정 WebSocket 연결로 메시지 전송"""
        try:
            await websocket.send_text(json.dumps(message, default=str))
            
            # 활동 시간 업데이트
            if websocket in self.connection_users:
                self.connection_users[websocket]["last_activity"] = datetime.utcnow()
                
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
            self.disconnect(websocket)

    async def send_to_user(self, user_id: int, message: dict):
        """특정 사용자의 모든 연결로 메시지 전송"""
        if user_id in self.active_connections:
            disconnected_connections = []
            
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(json.dumps(message, default=str))
                except:
                    disconnected_connections.append(connection)
            
            # 실패한 연결들 정리
            for connection in disconnected_connections:
                self.disconnect(connection)

    async def send_to_role(self, role: str, message: dict):
        """특정 역할의 모든 사용자에게 메시지 전송"""
        if role in self.connections_by_role:
            disconnected_connections = []
            
            for connection in self.connections_by_role[role].copy():
                try:
                    await connection.send_text(json.dumps(message, default=str))
                except:
                    disconnected_connections.append(connection)
            
            # 실패한 연결들 정리
            for connection in disconnected_connections:
                self.disconnect(connection)

    async def broadcast(self, message: dict):
        """모든 연결된 클라이언트에게 메시지 브로드캐스트"""
        disconnected_connections = []
        
        for user_connections in self.active_connections.values():
            for connection in user_connections:
                try:
                    await connection.send_text(json.dumps(message, default=str))
                except:
                    disconnected_connections.append(connection)
        
        # 실패한 연결들 정리
        for connection in disconnected_connections:
            self.disconnect(connection)

    async def notify_campaign_update(self, campaign_id: int, update_type: str, data: dict):
        """캠페인 업데이트 알림"""
        message = {
            "type": NotificationType.CAMPAIGN_UPDATE,
            "campaign_id": campaign_id,
            "update_type": update_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
            "title": f"캠페인 {update_type}",
            "message": f"캠페인 ID {campaign_id}가 업데이트되었습니다."
        }
        
        await self.broadcast(message)

    async def notify_purchase_request(self, request_id: int, status: str, user_id: Optional[int] = None):
        """구매요청 상태 변경 알림"""
        message = {
            "type": NotificationType.PURCHASE_REQUEST,
            "request_id": request_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "title": "구매요청 업데이트",
            "message": f"구매요청 #{request_id}의 상태가 '{status}'로 변경되었습니다."
        }
        
        if user_id:
            await self.send_to_user(user_id, message)
        else:
            await self.send_to_role("admin", message)

    async def notify_system_alert(self, alert_type: str, message: str, severity: str = "info"):
        """시스템 알림"""
        notification = {
            "type": NotificationType.SYSTEM_ALERT,
            "alert_type": alert_type,
            "severity": severity,
            "title": f"시스템 알림 ({severity.upper()})",
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if severity in ["critical", "error"]:
            await self.send_to_role("admin", notification)
        else:
            await self.broadcast(notification)

    async def notify_performance_alert(self, metric: str, value: float, threshold: float):
        """성능 경고 알림"""
        message = {
            "type": NotificationType.PERFORMANCE_ALERT,
            "metric": metric,
            "value": value,
            "threshold": threshold,
            "title": "성능 경고",
            "message": f"{metric} 지표가 임계값을 초과했습니다: {value} > {threshold}",
            "timestamp": datetime.utcnow().isoformat(),
            "severity": "warning"
        }
        
        await self.send_to_role("admin", message)

    async def notify_security_alert(self, alert_type: str, ip_address: str, details: dict):
        """보안 경고 알림"""
        message = {
            "type": NotificationType.SECURITY_ALERT,
            "alert_type": alert_type,
            "ip_address": ip_address,
            "details": details,
            "title": "보안 경고",
            "message": f"보안 위협 탐지: {alert_type} from {ip_address}",
            "timestamp": datetime.utcnow().isoformat(),
            "severity": "critical"
        }
        
        await self.send_to_role("admin", message)

    def get_connection_stats(self) -> dict:
        """연결 통계 정보 반환"""
        total_connections = sum(len(connections) for connections in self.active_connections.values())
        
        return {
            "total_users": len(self.active_connections),
            "total_connections": total_connections,
            "connections_by_role": {
                role: len(connections) 
                for role, connections in self.connections_by_role.items()
            },
            "active_users": list(self.active_connections.keys())
        }

    async def cleanup_stale_connections(self):
        """비활성 연결 정리 (주기적 실행)"""
        cutoff_time = datetime.utcnow().timestamp() - 300  # 5분
        stale_connections = []
        
        for websocket, user_info in self.connection_users.items():
            if user_info["last_activity"].timestamp() < cutoff_time:
                stale_connections.append(websocket)
        
        for connection in stale_connections:
            logger.info(f"Cleaning up stale WebSocket connection")
            self.disconnect(connection)
            try:
                await connection.close()
            except:
                pass

# 전역 연결 관리자 인스턴스
manager = ConnectionManager()

async def periodic_cleanup():
    """주기적인 연결 정리 작업"""
    while True:
        try:
            await manager.cleanup_stale_connections()
            await asyncio.sleep(300)  # 5분마다 실행
        except Exception as e:
            logger.error(f"Error during periodic cleanup: {e}")
            await asyncio.sleep(60)  # 오류 시 1분 후 재시도