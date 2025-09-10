# BrandFlow FastAPI v2.0.0 - 점진적 기능 복원
from fastapi import FastAPI, HTTPException, Depends, Request, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pydantic import BaseModel
import os
import logging
import hashlib
import sqlite3
import jwt
import datetime
import time
import psutil
import sys
import shutil
import uuid
import json
import asyncio
from typing import Optional, Dict, Any, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# JWT 설정
SECRET_KEY = os.getenv("JWT_SECRET", "brandflow-test-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 인증 스키마
security = HTTPBearer()

# 데이터베이스 연결 상태 추적
db_status = {"connected": False, "error": None, "tables_created": False}

# 모니터링 상태 추적
monitoring_stats = {
    "requests_count": 0,
    "total_processing_time": 0,
    "start_time": time.time(),
    "errors_count": 0
}

# WebSocket 연결 관리자
class WebSocketManager:
    def __init__(self):
        # 사용자별 활성 연결 {user_id: [websockets]}
        self.active_connections: Dict[int, List[WebSocket]] = {}
        # 전체 연결 추적
        self.all_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        
        # 사용자별 연결 추가
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        
        # 전체 연결 목록에 추가
        self.all_connections.append(websocket)
        
        logger.info(f"WebSocket connected for user {user_id}")
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        # 사용자별 연결에서 제거
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            
            # 사용자의 연결이 없으면 키 삭제
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        # 전체 연결 목록에서 제거
        if websocket in self.all_connections:
            self.all_connections.remove(websocket)
        
        logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_personal_message(self, message: str, user_id: int):
        """특정 사용자에게 메시지 전송"""
        if user_id in self.active_connections:
            disconnected = []
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_text(message)
                except:
                    disconnected.append(websocket)
            
            # 연결이 끊어진 WebSocket 정리
            for ws in disconnected:
                self.disconnect(ws, user_id)
    
    async def send_to_all(self, message: str):
        """모든 연결된 사용자에게 메시지 전송"""
        disconnected = []
        for websocket in self.all_connections:
            try:
                await websocket.send_text(message)
            except:
                disconnected.append(websocket)
        
        # 연결이 끊어진 WebSocket 정리
        for ws in disconnected:
            if ws in self.all_connections:
                self.all_connections.remove(ws)
    
    async def broadcast_notification(self, notification_data: Dict[str, Any], user_id: Optional[int] = None):
        """알림을 특정 사용자 또는 전체에게 브로드캐스트"""
        message = json.dumps({
            "type": "notification",
            "data": notification_data,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
        
        if user_id:
            await self.send_personal_message(message, user_id)
        else:
            await self.send_to_all(message)

# WebSocket 매니저 인스턴스
websocket_manager = WebSocketManager()

# 파일 업로드 설정
UPLOAD_DIR = "./uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {
    "images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
    "documents": [".pdf", ".doc", ".docx", ".txt", ".xlsx", ".xls", ".ppt", ".pptx"],
    "archives": [".zip", ".rar", ".7z"]
}
ALL_ALLOWED_EXTENSIONS = sum(ALLOWED_EXTENSIONS.values(), [])

# Pydantic 모델들
class LoginRequest(BaseModel):
    email: str
    password: str

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "user"

class Token(BaseModel):
    access_token: str
    token_type: str

class CampaignCreate(BaseModel):
    name: str
    description: str = ""
    client_company: str = ""
    budget: float = 0.0
    start_date: str = ""
    end_date: str = ""
    status: str = "active"

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    client_company: Optional[str] = None
    budget: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None

class NotificationCreate(BaseModel):
    title: str
    message: str
    type: str = "info"  # info, success, warning, error
    user_id: int
    related_campaign_id: Optional[int] = None

class PurchaseOrderCreate(BaseModel):
    campaign_id: int
    title: str
    description: str
    requested_amount: float
    vendor: str = ""
    category: str = "general"  # general, media, production, service
    priority: str = "medium"  # low, medium, high, urgent
    requested_delivery_date: str = ""
    
class PurchaseOrderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    requested_amount: Optional[float] = None
    vendor: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    approved_amount: Optional[float] = None
    approved_by: Optional[int] = None
    rejection_reason: Optional[str] = None
    requested_delivery_date: Optional[str] = None

class BackupRequest(BaseModel):
    description: Optional[str] = ""
    include_files: bool = True
    compress: bool = True

class RestoreRequest(BaseModel):
    backup_filename: str
    confirm_restore: bool = False

# 권한 관리 모델들
class RoleCreate(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    is_active: bool = True

class RoleUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class PermissionCreate(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    resource: str
    action: str

class UserRoleUpdate(BaseModel):
    user_id: int
    role: str

class UserPermissionGrant(BaseModel):
    user_id: int
    permission_name: str
    expires_at: Optional[str] = None

class UserStatusUpdate(BaseModel):
    user_id: int
    status: str  # 'active', 'inactive', 'locked'

# 백업 시스템 설정
BACKUP_DIR = "./backups"
MAX_BACKUP_COUNT = 10  # 최대 보관 백업 수

# 스케줄러 인스턴스
scheduler = AsyncIOScheduler()

# 백업 스케줄 설정
BACKUP_SCHEDULE_CONFIG = {
    "enabled": True,
    "daily_backup_time": "02:00",  # 매일 오전 2시
    "weekly_backup_day": "sunday",  # 매주 일요일
    "weekly_backup_time": "03:00",  # 오전 3시
    "auto_cleanup": True,
    "retention_days": 30,
    "notification_enabled": True
}

# 인증 헬퍼 함수들
def hash_password(password: str) -> str:
    """비밀번호 해시화"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
    """JWT 토큰 생성"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_user_by_email(email: str) -> Optional[dict]:
    """이메일로 사용자 조회"""
    if not db_status["connected"]:
        return None
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, hashed_password, role FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        if user:
            return {
                "id": user[0],
                "name": user[1],
                "email": user[2],
                "hashed_password": user[3],
                "role": user[4]
            }
        return None
    except Exception as e:
        logger.error(f"사용자 조회 오류: {e}")
        return None

def create_user(user_data: UserCreate) -> bool:
    """새 사용자 생성"""
    if not db_status["connected"]:
        return False
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, hashed_password, role) VALUES (?, ?, ?, ?)",
            (user_data.name, user_data.email, hash_password(user_data.password), user_data.role)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"사용자 생성 오류: {e}")
        return False

# 모니터링 헬퍼 함수들
def get_system_info() -> Dict[str, Any]:
    """시스템 정보 조회"""
    try:
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "uptime": time.time() - monitoring_stats["start_time"]
        }
    except Exception as e:
        logger.error(f"시스템 정보 조회 오류: {e}")
        return {"error": str(e)}

def get_database_stats() -> Dict[str, Any]:
    """데이터베이스 통계 조회"""
    if not db_status["connected"]:
        return {"error": "Database not connected"}
    
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        # 사용자 수
        cursor.execute("SELECT COUNT(*) FROM users")
        users_count = cursor.fetchone()[0]
        
        # 캠페인 수
        cursor.execute("SELECT COUNT(*) FROM campaigns")
        campaigns_count = cursor.fetchone()[0]
        
        # 활성 캠페인 수
        cursor.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'active'")
        active_campaigns = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "users_count": users_count,
            "campaigns_count": campaigns_count,
            "active_campaigns": active_campaigns
        }
    except Exception as e:
        logger.error(f"데이터베이스 통계 조회 오류: {e}")
        return {"error": str(e)}

# 캠페인 CRUD 헬퍼 함수들
def create_campaign(campaign_data: CampaignCreate, creator_id: int) -> Optional[int]:
    """새 캠페인 생성"""
    if not db_status["connected"]:
        return None
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO campaigns (name, description, client_company, budget, 
                                 start_date, end_date, status, creator_id) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            campaign_data.name, campaign_data.description, campaign_data.client_company,
            campaign_data.budget, campaign_data.start_date, campaign_data.end_date,
            campaign_data.status, creator_id
        ))
        campaign_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return campaign_id
    except Exception as e:
        logger.error(f"캠페인 생성 오류: {e}")
        return None

def update_campaign(campaign_id: int, campaign_data: CampaignUpdate) -> bool:
    """캠페인 업데이트"""
    if not db_status["connected"]:
        return False
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        # 업데이트할 필드들만 처리
        update_fields = []
        params = []
        
        for field, value in campaign_data.dict(exclude_none=True).items():
            update_fields.append(f"{field} = ?")
            params.append(value)
        
        if not update_fields:
            return True  # 업데이트할 내용이 없으면 성공으로 처리
        
        params.append(campaign_id)
        query = f"UPDATE campaigns SET {', '.join(update_fields)} WHERE id = ?"
        
        cursor.execute(query, params)
        conn.commit()
        affected_rows = cursor.rowcount
        conn.close()
        
        return affected_rows > 0
    except Exception as e:
        logger.error(f"캠페인 업데이트 오류: {e}")
        return False

def delete_campaign(campaign_id: int) -> bool:
    """캠페인 삭제"""
    if not db_status["connected"]:
        return False
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
        conn.commit()
        affected_rows = cursor.rowcount
        conn.close()
        return affected_rows > 0
    except Exception as e:
        logger.error(f"캠페인 삭제 오류: {e}")
        return False

def get_campaign_by_id(campaign_id: int) -> Optional[dict]:
    """ID로 캠페인 조회"""
    if not db_status["connected"]:
        return None
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, u.name as creator_name 
            FROM campaigns c 
            LEFT JOIN users u ON c.creator_id = u.id
            WHERE c.id = ?
        """, (campaign_id,))
        campaign = cursor.fetchone()
        conn.close()
        
        if campaign:
            return {
                "id": campaign[0],
                "name": campaign[1],
                "description": campaign[2],
                "client_company": campaign[3],
                "budget": campaign[4],
                "start_date": campaign[5],
                "end_date": campaign[6],
                "status": campaign[7],
                "creator_id": campaign[8],
                "created_at": campaign[9],
                "creator_name": campaign[10]
            }
        return None
    except Exception as e:
        logger.error(f"캠페인 조회 오류: {e}")
        return None

# 알림 시스템 헬퍼 함수들
def create_notification(notification_data: NotificationCreate) -> Optional[int]:
    """새 알림 생성 및 실시간 WebSocket 전송"""
    if not db_status["connected"]:
        return None
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notifications (title, message, type, user_id, related_campaign_id) 
            VALUES (?, ?, ?, ?, ?)
        """, (
            notification_data.title, notification_data.message, notification_data.type,
            notification_data.user_id, notification_data.related_campaign_id
        ))
        notification_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # WebSocket을 통한 실시간 알림 전송
        if notification_id:
            asyncio.create_task(send_realtime_notification({
                "id": notification_id,
                "title": notification_data.title,
                "message": notification_data.message,
                "type": notification_data.type,
                "user_id": notification_data.user_id,
                "related_campaign_id": notification_data.related_campaign_id,
                "created_at": datetime.datetime.utcnow().isoformat(),
                "read": False
            }, notification_data.user_id))
        
        return notification_id
    except Exception as e:
        logger.error(f"알림 생성 오류: {e}")
        return None

async def send_realtime_notification(notification_data: Dict[str, Any], user_id: int):
    """실시간 알림 전송 헬퍼 함수"""
    try:
        await websocket_manager.broadcast_notification(notification_data, user_id)
        logger.info(f"실시간 알림 전송 완료: user_id={user_id}, title={notification_data.get('title')}")
    except Exception as e:
        logger.error(f"실시간 알림 전송 오류: {e}")

def get_user_notifications(user_id: int, unread_only: bool = False) -> list:
    """사용자 알림 목록 조회"""
    if not db_status["connected"]:
        return []
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        query = """
            SELECT n.*, c.name as campaign_name
            FROM notifications n
            LEFT JOIN campaigns c ON n.related_campaign_id = c.id
            WHERE n.user_id = ?
        """
        params = [user_id]
        
        if unread_only:
            query += " AND n.is_read = 0"
        
        query += " ORDER BY n.created_at DESC"
        
        cursor.execute(query, params)
        notifications = cursor.fetchall()
        conn.close()
        
        return [
            {
                "id": notif[0],
                "title": notif[1],
                "message": notif[2],
                "type": notif[3],
                "user_id": notif[4],
                "related_campaign_id": notif[5],
                "is_read": bool(notif[6]),
                "created_at": notif[7],
                "campaign_name": notif[8]
            } for notif in notifications
        ]
    except Exception as e:
        logger.error(f"알림 목록 조회 오류: {e}")
        return []

def mark_notification_read(notification_id: int, user_id: int) -> bool:
    """알림 읽음 처리"""
    if not db_status["connected"]:
        return False
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
            (notification_id, user_id)
        )
        conn.commit()
        affected_rows = cursor.rowcount
        conn.close()
        return affected_rows > 0
    except Exception as e:
        logger.error(f"알림 읽음 처리 오류: {e}")
        return False

def get_unread_count(user_id: int) -> int:
    """읽지 않은 알림 수 조회"""
    if not db_status["connected"]:
        return 0
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        logger.error(f"읽지 않은 알림 수 조회 오류: {e}")
        return 0

# 알림 자동 생성 함수
def notify_campaign_created(campaign_id: int, creator_id: int, campaign_name: str):
    """캠페인 생성 알림"""
    notification = NotificationCreate(
        title="새 캠페인 생성",
        message=f"'{campaign_name}' 캠페인이 성공적으로 생성되었습니다.",
        type="success",
        user_id=creator_id,
        related_campaign_id=campaign_id
    )
    create_notification(notification)

def notify_campaign_updated(campaign_id: int, user_id: int, campaign_name: str):
    """캠페인 업데이트 알림"""
    notification = NotificationCreate(
        title="캠페인 업데이트",
        message=f"'{campaign_name}' 캠페인이 업데이트되었습니다.",
        type="info",
        user_id=user_id,
        related_campaign_id=campaign_id
    )
    create_notification(notification)

# 파일 업로드 헬퍼 함수들
def is_allowed_file(filename: str) -> bool:
    """허용된 파일 확장자 확인"""
    if not filename:
        return False
    ext = os.path.splitext(filename.lower())[1]
    return ext in ALL_ALLOWED_EXTENSIONS

def get_file_category(filename: str) -> str:
    """파일 카테고리 결정"""
    ext = os.path.splitext(filename.lower())[1]
    for category, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return category
    return "other"

def save_uploaded_file(file: UploadFile, uploader_id: int, campaign_id: Optional[int] = None, description: str = "") -> Optional[dict]:
    """파일 업로드 및 DB 저장"""
    if not db_status["connected"]:
        return None
        
    try:
        # 파일 크기 확인
        file.file.seek(0, 2)  # 파일 끝으로 이동
        file_size = file.file.tell()
        file.file.seek(0)  # 파일 시작으로 다시 이동
        
        if file_size > MAX_FILE_SIZE:
            return None
            
        # 안전한 파일명 생성
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # 파일 저장
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # DB에 파일 정보 저장
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO files (filename, original_filename, file_path, file_size, 
                             file_type, mime_type, uploader_id, related_campaign_id, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            unique_filename, file.filename, file_path, file_size,
            get_file_category(file.filename), file.content_type,
            uploader_id, campaign_id, description
        ))
        
        file_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            "id": file_id,
            "filename": unique_filename,
            "original_filename": file.filename,
            "file_size": file_size,
            "file_type": get_file_category(file.filename),
            "mime_type": file.content_type
        }
        
    except Exception as e:
        logger.error(f"파일 업로드 오류: {e}")
        # 오류 시 파일 정리
        try:
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass
        return None

def get_user_files(user_id: int, campaign_id: Optional[int] = None) -> list:
    """사용자 파일 목록 조회"""
    if not db_status["connected"]:
        return []
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        query = """
            SELECT f.*, c.name as campaign_name, u.name as uploader_name
            FROM files f
            LEFT JOIN campaigns c ON f.related_campaign_id = c.id
            LEFT JOIN users u ON f.uploader_id = u.id
            WHERE f.uploader_id = ?
        """
        params = [user_id]
        
        if campaign_id:
            query += " AND f.related_campaign_id = ?"
            params.append(campaign_id)
            
        query += " ORDER BY f.created_at DESC"
        
        cursor.execute(query, params)
        files = cursor.fetchall()
        conn.close()
        
        return [
            {
                "id": f[0],
                "filename": f[1],
                "original_filename": f[2],
                "file_path": f[3],
                "file_size": f[4],
                "file_type": f[5],
                "mime_type": f[6],
                "uploader_id": f[7],
                "related_campaign_id": f[8],
                "description": f[9],
                "created_at": f[10],
                "campaign_name": f[11],
                "uploader_name": f[12]
            } for f in files
        ]
    except Exception as e:
        logger.error(f"파일 목록 조회 오류: {e}")
        return []

def get_file_by_id(file_id: int) -> Optional[dict]:
    """파일 정보 조회"""
    if not db_status["connected"]:
        return None
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.*, c.name as campaign_name, u.name as uploader_name
            FROM files f
            LEFT JOIN campaigns c ON f.related_campaign_id = c.id
            LEFT JOIN users u ON f.uploader_id = u.id
            WHERE f.id = ?
        """, (file_id,))
        file_data = cursor.fetchone()
        conn.close()
        
        if file_data:
            return {
                "id": file_data[0],
                "filename": file_data[1],
                "original_filename": file_data[2],
                "file_path": file_data[3],
                "file_size": file_data[4],
                "file_type": file_data[5],
                "mime_type": file_data[6],
                "uploader_id": file_data[7],
                "related_campaign_id": file_data[8],
                "description": file_data[9],
                "created_at": file_data[10],
                "campaign_name": file_data[11],
                "uploader_name": file_data[12]
            }
        return None
    except Exception as e:
        logger.error(f"파일 조회 오류: {e}")
        return None

# 발주관리 헬퍼 함수들
def create_purchase_order(po_data: PurchaseOrderCreate, requester_id: int) -> Optional[int]:
    """새 발주요청 생성"""
    if not db_status["connected"]:
        return None
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO purchase_orders (campaign_id, title, description, requested_amount,
                                       vendor, category, priority, requester_id, requested_delivery_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            po_data.campaign_id, po_data.title, po_data.description, po_data.requested_amount,
            po_data.vendor, po_data.category, po_data.priority, requester_id, po_data.requested_delivery_date
        ))
        po_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return po_id
    except Exception as e:
        logger.error(f"발주요청 생성 오류: {e}")
        return None

def get_purchase_orders(campaign_id: Optional[int] = None, status: Optional[str] = None) -> list:
    """발주요청 목록 조회"""
    if not db_status["connected"]:
        return []
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        query = """
            SELECT po.*, c.name as campaign_name, u1.name as requester_name, u2.name as approver_name
            FROM purchase_orders po
            LEFT JOIN campaigns c ON po.campaign_id = c.id
            LEFT JOIN users u1 ON po.requester_id = u1.id
            LEFT JOIN users u2 ON po.approved_by = u2.id
            WHERE 1=1
        """
        params = []
        
        if campaign_id:
            query += " AND po.campaign_id = ?"
            params.append(campaign_id)
            
        if status:
            query += " AND po.status = ?"
            params.append(status)
            
        query += " ORDER BY po.created_at DESC"
        
        cursor.execute(query, params)
        orders = cursor.fetchall()
        conn.close()
        
        return [
            {
                "id": order[0],
                "campaign_id": order[1],
                "title": order[2],
                "description": order[3],
                "requested_amount": order[4],
                "approved_amount": order[5],
                "vendor": order[6],
                "category": order[7],
                "priority": order[8],
                "status": order[9],
                "requester_id": order[10],
                "approved_by": order[11],
                "rejection_reason": order[12],
                "requested_delivery_date": order[13],
                "approved_date": order[14],
                "created_at": order[15],
                "campaign_name": order[16],
                "requester_name": order[17],
                "approver_name": order[18]
            } for order in orders
        ]
    except Exception as e:
        logger.error(f"발주요청 목록 조회 오류: {e}")
        return []

def get_purchase_order_by_id(po_id: int) -> Optional[dict]:
    """발주요청 상세 조회"""
    if not db_status["connected"]:
        return None
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT po.*, c.name as campaign_name, u1.name as requester_name, u2.name as approver_name
            FROM purchase_orders po
            LEFT JOIN campaigns c ON po.campaign_id = c.id
            LEFT JOIN users u1 ON po.requester_id = u1.id
            LEFT JOIN users u2 ON po.approved_by = u2.id
            WHERE po.id = ?
        """, (po_id,))
        order = cursor.fetchone()
        conn.close()
        
        if order:
            return {
                "id": order[0],
                "campaign_id": order[1],
                "title": order[2],
                "description": order[3],
                "requested_amount": order[4],
                "approved_amount": order[5],
                "vendor": order[6],
                "category": order[7],
                "priority": order[8],
                "status": order[9],
                "requester_id": order[10],
                "approved_by": order[11],
                "rejection_reason": order[12],
                "requested_delivery_date": order[13],
                "approved_date": order[14],
                "created_at": order[15],
                "campaign_name": order[16],
                "requester_name": order[17],
                "approver_name": order[18]
            }
        return None
    except Exception as e:
        logger.error(f"발주요청 조회 오류: {e}")
        return None

def update_purchase_order(po_id: int, po_data: PurchaseOrderUpdate) -> bool:
    """발주요청 업데이트"""
    if not db_status["connected"]:
        return False
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        update_fields = []
        params = []
        
        for field, value in po_data.dict(exclude_none=True).items():
            update_fields.append(f"{field} = ?")
            params.append(value)
        
        if not update_fields:
            return True
        
        params.append(po_id)
        query = f"UPDATE purchase_orders SET {', '.join(update_fields)} WHERE id = ?"
        
        cursor.execute(query, params)
        conn.commit()
        affected_rows = cursor.rowcount
        conn.close()
        
        return affected_rows > 0
    except Exception as e:
        logger.error(f"발주요청 업데이트 오류: {e}")
        return False

def approve_purchase_order(po_id: int, approver_id: int, approved_amount: float) -> bool:
    """발주요청 승인"""
    if not db_status["connected"]:
        return False
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE purchase_orders 
            SET status = 'approved', approved_by = ?, approved_amount = ?, approved_date = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (approver_id, approved_amount, po_id))
        conn.commit()
        affected_rows = cursor.rowcount
        conn.close()
        return affected_rows > 0
    except Exception as e:
        logger.error(f"발주요청 승인 오류: {e}")
        return False

def reject_purchase_order(po_id: int, approver_id: int, reason: str) -> bool:
    """발주요청 거부"""
    if not db_status["connected"]:
        return False
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE purchase_orders 
            SET status = 'rejected', approved_by = ?, rejection_reason = ?, approved_date = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (approver_id, reason, po_id))
        conn.commit()
        affected_rows = cursor.rowcount
        conn.close()
        return affected_rows > 0
    except Exception as e:
        logger.error(f"발주요청 거부 오류: {e}")
        return False

# 발주 알림 자동 생성 함수
def notify_purchase_order_created(po_id: int, campaign_id: int, requester_id: int, po_title: str):
    """발주요청 생성 알림"""
    notification = NotificationCreate(
        title="새 발주요청",
        message=f"'{po_title}' 발주요청이 생성되었습니다.",
        type="info",
        user_id=requester_id,
        related_campaign_id=campaign_id
    )
    create_notification(notification)

def notify_purchase_order_approved(po_id: int, campaign_id: int, requester_id: int, po_title: str, approved_amount: float):
    """발주요청 승인 알림"""
    notification = NotificationCreate(
        title="발주요청 승인",
        message=f"'{po_title}' 발주요청이 {approved_amount:,.0f}원으로 승인되었습니다.",
        type="success",
        user_id=requester_id,
        related_campaign_id=campaign_id
    )
    create_notification(notification)

def notify_purchase_order_rejected(po_id: int, campaign_id: int, requester_id: int, po_title: str, reason: str):
    """발주요청 거부 알림"""
    notification = NotificationCreate(
        title="발주요청 거부",
        message=f"'{po_title}' 발주요청이 거부되었습니다. 사유: {reason}",
        type="warning",
        user_id=requester_id,
        related_campaign_id=campaign_id
    )
    create_notification(notification)

# 백업 및 복원 시스템 헬퍼 함수들
def create_database_backup(description: str = "", include_files: bool = True, compress: bool = True) -> Dict[str, Any]:
    """데이터베이스 백업 생성"""
    try:
        # 백업 디렉토리 생성
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # 백업 파일명 생성 (타임스탬프 기반)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"brandflow_backup_{timestamp}"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        
        # 백업 메타데이터
        backup_info = {
            "backup_name": backup_name,
            "created_at": datetime.datetime.now().isoformat(),
            "description": description,
            "include_files": include_files,
            "compressed": compress,
            "database_size": 0,
            "files_count": 0,
            "total_size": 0,
            "tables_backed_up": []
        }
        
        # 데이터베이스 백업
        if db_status["connected"]:
            db_source = "./data/brandflow.db"
            db_backup = f"{backup_path}_database.db"
            
            if os.path.exists(db_source):
                shutil.copy2(db_source, db_backup)
                backup_info["database_size"] = os.path.getsize(db_backup)
                backup_info["total_size"] += backup_info["database_size"]
                
                # 백업된 테이블 목록 조회
                backup_info["tables_backed_up"] = get_backed_up_tables(db_backup)
        
        # 파일 백업 (선택 사항)
        if include_files and os.path.exists("./uploads"):
            files_backup = f"{backup_path}_files"
            shutil.copytree("./uploads", files_backup)
            
            # 파일 수 및 크기 계산
            files_count = 0
            files_size = 0
            for root, dirs, files in os.walk(files_backup):
                files_count += len(files)
                for file in files:
                    file_path = os.path.join(root, file)
                    files_size += os.path.getsize(file_path)
            
            backup_info["files_count"] = files_count
            backup_info["total_size"] += files_size
        
        # 압축 처리
        if compress:
            compressed_path = f"{backup_path}.zip"
            shutil.make_archive(backup_path, 'zip', BACKUP_DIR, f"{backup_name}*")
            
            # 원본 파일들 삭제
            if os.path.exists(f"{backup_path}_database.db"):
                os.remove(f"{backup_path}_database.db")
            if os.path.exists(f"{backup_path}_files"):
                shutil.rmtree(f"{backup_path}_files")
            
            backup_info["compressed"] = True
            backup_info["total_size"] = os.path.getsize(compressed_path)
            backup_info["backup_file"] = f"{backup_name}.zip"
        else:
            backup_info["backup_file"] = backup_name
        
        # 백업 메타데이터 저장
        metadata_path = os.path.join(BACKUP_DIR, f"{backup_name}_metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(backup_info, f, indent=2, ensure_ascii=False)
        
        # 오래된 백업 정리
        cleanup_old_backups()
        
        logger.info(f"백업 생성 완료: {backup_info['backup_file']}")
        return backup_info
        
    except Exception as e:
        logger.error(f"백업 생성 오류: {e}")
        return {"error": str(e)}

def get_backed_up_tables(db_path: str) -> List[str]:
    """백업된 데이터베이스의 테이블 목록 조회"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tables
    except Exception as e:
        logger.error(f"테이블 목록 조회 오류: {e}")
        return []

def list_available_backups() -> List[Dict[str, Any]]:
    """사용 가능한 백업 목록 조회"""
    try:
        backups = []
        if not os.path.exists(BACKUP_DIR):
            return backups
        
        for file in os.listdir(BACKUP_DIR):
            if file.endswith('_metadata.json'):
                metadata_path = os.path.join(BACKUP_DIR, file)
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        backup_info = json.load(f)
                    
                    # 백업 파일 존재 확인
                    backup_file_path = os.path.join(BACKUP_DIR, backup_info['backup_file'])
                    if os.path.exists(backup_file_path):
                        backup_info['file_exists'] = True
                        backup_info['file_size'] = os.path.getsize(backup_file_path)
                    else:
                        backup_info['file_exists'] = False
                    
                    backups.append(backup_info)
                except Exception as e:
                    logger.error(f"백업 메타데이터 읽기 오류: {e}")
        
        # 생성일 기준 정렬 (최신순)
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        return backups
        
    except Exception as e:
        logger.error(f"백업 목록 조회 오류: {e}")
        return []

def restore_database_backup(backup_filename: str) -> Dict[str, Any]:
    """데이터베이스 백업 복원"""
    try:
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        if not os.path.exists(backup_path):
            return {"success": False, "error": "백업 파일을 찾을 수 없습니다"}
        
        # 현재 데이터베이스 백업 (복원 전 안전장치)
        current_backup = create_database_backup(
            description="복원 전 자동 백업", 
            include_files=False, 
            compress=True
        )
        
        restore_info = {
            "backup_filename": backup_filename,
            "restored_at": datetime.datetime.now().isoformat(),
            "pre_restore_backup": current_backup.get("backup_file"),
            "success": False
        }
        
        # 압축 파일인 경우 압축 해제
        if backup_filename.endswith('.zip'):
            import zipfile
            temp_dir = os.path.join(BACKUP_DIR, "temp_restore")
            os.makedirs(temp_dir, exist_ok=True)
            
            with zipfile.ZipFile(backup_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # 데이터베이스 파일 찾기
            db_file = None
            for file in os.listdir(temp_dir):
                if file.endswith('_database.db'):
                    db_file = os.path.join(temp_dir, file)
                    break
            
            if db_file and os.path.exists(db_file):
                # 기존 데이터베이스 교체
                target_db = "./data/brandflow.db"
                os.makedirs("./data", exist_ok=True)
                shutil.copy2(db_file, target_db)
                restore_info["success"] = True
                restore_info["message"] = "데이터베이스가 성공적으로 복원되었습니다"
            
            # 파일들 복원 (있는 경우)
            files_dir = None
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                if os.path.isdir(item_path) and item.endswith('_files'):
                    files_dir = item_path
                    break
            
            if files_dir and os.path.exists(files_dir):
                target_uploads = "./uploads"
                if os.path.exists(target_uploads):
                    shutil.rmtree(target_uploads)
                shutil.copytree(files_dir, target_uploads)
                restore_info["files_restored"] = True
            
            # 임시 디렉토리 정리
            shutil.rmtree(temp_dir)
        
        else:
            # 비압축 백업 처리
            db_backup = f"{backup_path}_database.db"
            if os.path.exists(db_backup):
                target_db = "./data/brandflow.db"
                os.makedirs("./data", exist_ok=True)
                shutil.copy2(db_backup, target_db)
                restore_info["success"] = True
                restore_info["message"] = "데이터베이스가 성공적으로 복원되었습니다"
        
        if restore_info["success"]:
            logger.info(f"백업 복원 완료: {backup_filename}")
        else:
            restore_info["error"] = "복원 가능한 데이터베이스 파일을 찾을 수 없습니다"
        
        return restore_info
        
    except Exception as e:
        logger.error(f"백업 복원 오류: {e}")
        return {"success": False, "error": str(e)}

def cleanup_old_backups():
    """오래된 백업 파일 정리"""
    try:
        backups = list_available_backups()
        if len(backups) > MAX_BACKUP_COUNT:
            # 오래된 백업부터 삭제
            backups_to_delete = backups[MAX_BACKUP_COUNT:]
            for backup in backups_to_delete:
                backup_file = os.path.join(BACKUP_DIR, backup['backup_file'])
                metadata_file = os.path.join(BACKUP_DIR, f"{backup['backup_name']}_metadata.json")
                
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                if os.path.exists(metadata_file):
                    os.remove(metadata_file)
                
                logger.info(f"오래된 백업 삭제: {backup['backup_file']}")
    
    except Exception as e:
        logger.error(f"백업 정리 오류: {e}")

def verify_backup_integrity(backup_filename: str) -> Dict[str, Any]:
    """백업 파일 무결성 검증"""
    try:
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        if not os.path.exists(backup_path):
            return {"valid": False, "error": "백업 파일을 찾을 수 없습니다"}
        
        verification_result = {
            "backup_filename": backup_filename,
            "valid": False,
            "checks": {
                "file_exists": True,
                "file_readable": False,
                "database_valid": False,
                "metadata_exists": False,
                "size_match": False
            },
            "details": {}
        }
        
        # 파일 읽기 가능 확인
        try:
            with open(backup_path, 'rb') as f:
                f.read(1024)  # 첫 1KB 읽기 테스트
            verification_result["checks"]["file_readable"] = True
        except:
            return verification_result
        
        # 메타데이터 존재 확인
        metadata_name = backup_filename.replace('.zip', '_metadata.json').replace('.db', '_metadata.json')
        metadata_path = os.path.join(BACKUP_DIR, metadata_name)
        
        if os.path.exists(metadata_path):
            verification_result["checks"]["metadata_exists"] = True
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                verification_result["details"]["metadata"] = metadata
                
                # 크기 비교
                actual_size = os.path.getsize(backup_path)
                expected_size = metadata.get("total_size", 0)
                if abs(actual_size - expected_size) < 1024:  # 1KB 오차 허용
                    verification_result["checks"]["size_match"] = True
                verification_result["details"]["actual_size"] = actual_size
                verification_result["details"]["expected_size"] = expected_size
            except:
                pass
        
        # 압축 파일 내부 검증 (ZIP 파일인 경우)
        if backup_filename.endswith('.zip'):
            try:
                import zipfile
                with zipfile.ZipFile(backup_path, 'r') as zip_ref:
                    # ZIP 파일 무결성 검사
                    zip_ref.testzip()
                    file_list = zip_ref.namelist()
                    verification_result["details"]["zip_files"] = file_list
                    
                    # 데이터베이스 파일 확인
                    db_files = [f for f in file_list if f.endswith('_database.db')]
                    if db_files:
                        verification_result["checks"]["database_valid"] = True
                
            except Exception as e:
                verification_result["details"]["zip_error"] = str(e)
        
        # 전체 검증 결과
        verification_result["valid"] = all([
            verification_result["checks"]["file_exists"],
            verification_result["checks"]["file_readable"],
            verification_result["checks"]["database_valid"]
        ])
        
        return verification_result
        
    except Exception as e:
        logger.error(f"백업 무결성 검증 오류: {e}")
        return {"valid": False, "error": str(e)}

# 권한 관리 시스템 함수들
async def init_roles_and_permissions():
    """기본 역할 및 권한 초기화"""
    if not db_status["connected"]:
        logger.warning("데이터베이스 연결되지 않음 - 권한 초기화 생략")
        return
    
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        # 기본 역할 생성
        default_roles = [
            ("super_admin", "최고 관리자", "시스템의 모든 권한을 가진 최고 관리자"),
            ("admin", "관리자", "시스템 관리 권한을 가진 관리자"),
            ("manager", "매니저", "캠페인 관리 권한을 가진 매니저"),
            ("user", "사용자", "기본 사용자 권한"),
            ("viewer", "뷰어", "읽기 전용 사용자")
        ]
        
        for role_name, display_name, description in default_roles:
            cursor.execute("""
                INSERT OR IGNORE INTO roles (name, display_name, description, is_active)
                VALUES (?, ?, ?, 1)
            """, (role_name, display_name, description))
        
        # 기본 권한 생성
        default_permissions = [
            # 사용자 관리
            ("user.create", "사용자 생성", "새로운 사용자를 생성할 수 있습니다", "user", "create"),
            ("user.read", "사용자 조회", "사용자 정보를 조회할 수 있습니다", "user", "read"),
            ("user.update", "사용자 수정", "사용자 정보를 수정할 수 있습니다", "user", "update"),
            ("user.delete", "사용자 삭제", "사용자를 삭제할 수 있습니다", "user", "delete"),
            ("user.manage_roles", "사용자 역할 관리", "사용자의 역할을 변경할 수 있습니다", "user", "manage_roles"),
            
            # 캠페인 관리
            ("campaign.create", "캠페인 생성", "새로운 캠페인을 생성할 수 있습니다", "campaign", "create"),
            ("campaign.read", "캠페인 조회", "캠페인 정보를 조회할 수 있습니다", "campaign", "read"),
            ("campaign.update", "캠페인 수정", "캠페인 정보를 수정할 수 있습니다", "campaign", "update"),
            ("campaign.delete", "캠페인 삭제", "캠페인을 삭제할 수 있습니다", "campaign", "delete"),
            ("campaign.approve", "캠페인 승인", "캠페인을 승인할 수 있습니다", "campaign", "approve"),
            
            # 발주 관리
            ("purchase_order.create", "발주 생성", "발주 요청을 생성할 수 있습니다", "purchase_order", "create"),
            ("purchase_order.read", "발주 조회", "발주 정보를 조회할 수 있습니다", "purchase_order", "read"),
            ("purchase_order.update", "발주 수정", "발주 정보를 수정할 수 있습니다", "purchase_order", "update"),
            ("purchase_order.delete", "발주 삭제", "발주를 삭제할 수 있습니다", "purchase_order", "delete"),
            ("purchase_order.approve", "발주 승인", "발주 요청을 승인할 수 있습니다", "purchase_order", "approve"),
            
            # 백업 관리
            ("backup.create", "백업 생성", "데이터베이스 백업을 생성할 수 있습니다", "backup", "create"),
            ("backup.read", "백업 조회", "백업 목록과 정보를 조회할 수 있습니다", "backup", "read"),
            ("backup.restore", "백업 복원", "백업에서 데이터를 복원할 수 있습니다", "backup", "restore"),
            ("backup.delete", "백업 삭제", "백업 파일을 삭제할 수 있습니다", "backup", "delete"),
            ("backup.schedule", "백업 스케줄", "백업 스케줄을 관리할 수 있습니다", "backup", "schedule"),
            
            # 시스템 관리
            ("system.monitor", "시스템 모니터링", "시스템 상태를 모니터링할 수 있습니다", "system", "monitor"),
            ("system.admin", "시스템 관리", "시스템 설정을 관리할 수 있습니다", "system", "admin"),
            ("system.logs", "로그 조회", "시스템 로그를 조회할 수 있습니다", "system", "logs"),
            
            # 알림 관리
            ("notification.read", "알림 조회", "알림을 조회할 수 있습니다", "notification", "read"),
            ("notification.send", "알림 전송", "알림을 전송할 수 있습니다", "notification", "send"),
        ]
        
        for perm_name, display_name, description, resource, action in default_permissions:
            cursor.execute("""
                INSERT OR IGNORE INTO permissions (name, display_name, description, resource, action)
                VALUES (?, ?, ?, ?, ?)
            """, (perm_name, display_name, description, resource, action))
        
        # 역할별 기본 권한 할당
        role_permission_mappings = {
            "super_admin": [  # 최고 관리자 - 모든 권한
                "user.create", "user.read", "user.update", "user.delete", "user.manage_roles",
                "campaign.create", "campaign.read", "campaign.update", "campaign.delete", "campaign.approve",
                "purchase_order.create", "purchase_order.read", "purchase_order.update", "purchase_order.delete", "purchase_order.approve",
                "backup.create", "backup.read", "backup.restore", "backup.delete", "backup.schedule",
                "system.monitor", "system.admin", "system.logs",
                "notification.read", "notification.send"
            ],
            "admin": [  # 관리자 - 대부분의 권한 (사용자 삭제 제외)
                "user.create", "user.read", "user.update", "user.manage_roles",
                "campaign.create", "campaign.read", "campaign.update", "campaign.delete", "campaign.approve",
                "purchase_order.create", "purchase_order.read", "purchase_order.update", "purchase_order.delete", "purchase_order.approve",
                "backup.create", "backup.read", "backup.restore", "backup.delete", "backup.schedule",
                "system.monitor", "system.logs",
                "notification.read", "notification.send"
            ],
            "manager": [  # 매니저 - 업무 관련 권한
                "user.read",
                "campaign.create", "campaign.read", "campaign.update", "campaign.approve",
                "purchase_order.create", "purchase_order.read", "purchase_order.update", "purchase_order.approve",
                "backup.read",
                "system.monitor",
                "notification.read", "notification.send"
            ],
            "user": [  # 사용자 - 기본 권한
                "campaign.read", "campaign.create", "campaign.update",
                "purchase_order.create", "purchase_order.read", "purchase_order.update",
                "notification.read"
            ],
            "viewer": [  # 뷰어 - 읽기 전용
                "campaign.read",
                "purchase_order.read",
                "notification.read"
            ]
        }
        
        # 역할-권한 매핑 생성
        for role_name, permissions in role_permission_mappings.items():
            # 역할 ID 조회
            cursor.execute("SELECT id FROM roles WHERE name = ?", (role_name,))
            role_result = cursor.fetchone()
            if not role_result:
                continue
            role_id = role_result[0]
            
            # 권한 할당
            for perm_name in permissions:
                cursor.execute("SELECT id FROM permissions WHERE name = ?", (perm_name,))
                perm_result = cursor.fetchone()
                if not perm_result:
                    continue
                perm_id = perm_result[0]
                
                cursor.execute("""
                    INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                    VALUES (?, ?)
                """, (role_id, perm_id))
        
        conn.commit()
        conn.close()
        logger.info("SUCCESS 기본 역할 및 권한 초기화 완료")
        
    except Exception as e:
        logger.error(f"역할 및 권한 초기화 오류: {e}")

def get_user_permissions(user_id: int) -> List[str]:
    """사용자의 모든 권한 목록 조회 (역할 권한 + 개별 권한)"""
    if not db_status["connected"]:
        return []
    
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        permissions = set()
        
        # 사용자 역할을 통한 권한 조회
        cursor.execute("""
            SELECT DISTINCT p.name
            FROM users u
            JOIN roles r ON u.role = r.name
            JOIN role_permissions rp ON r.id = rp.role_id
            JOIN permissions p ON rp.permission_id = p.id
            WHERE u.id = ? AND r.is_active = 1
        """, (user_id,))
        
        for row in cursor.fetchall():
            permissions.add(row[0])
        
        # 사용자별 개별 권한 조회 (만료되지 않은 것만)
        cursor.execute("""
            SELECT DISTINCT p.name
            FROM user_permissions up
            JOIN permissions p ON up.permission_id = p.id
            WHERE up.user_id = ? 
            AND (up.expires_at IS NULL OR up.expires_at > CURRENT_TIMESTAMP)
        """, (user_id,))
        
        for row in cursor.fetchall():
            permissions.add(row[0])
        
        conn.close()
        return list(permissions)
        
    except Exception as e:
        logger.error(f"사용자 권한 조회 오류: {e}")
        return []

def has_permission(user_id: int, permission: str) -> bool:
    """사용자가 특정 권한을 가지고 있는지 확인"""
    user_permissions = get_user_permissions(user_id)
    return permission in user_permissions

def require_permission(permission: str):
    """권한 검증 데코레이터를 위한 의존성"""
    def permission_dependency(current_user = Depends(get_current_user_dependency)):
        if not has_permission(current_user["id"], permission):
            raise HTTPException(
                status_code=403, 
                detail=f"권한이 부족합니다. 필요한 권한: {permission}"
            )
        return current_user
    return permission_dependency

# 활동 로그 및 감사 추적 함수들
def log_activity(
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    action: str = "",
    resource: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: str = "success",
    error_message: Optional[str] = None,
    session_id: Optional[str] = None
):
    """사용자 활동 로그 기록"""
    if not db_status["connected"]:
        return
    
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO activity_logs (
                user_id, username, action, resource, resource_id, details,
                ip_address, user_agent, status, error_message, session_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, username, action, resource, resource_id, details,
            ip_address, user_agent, status, error_message, session_id
        ))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"활동 로그 기록 오류: {e}")

def log_login_attempt(
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    email: Optional[str] = None,
    status: str = "success",
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    failure_reason: Optional[str] = None,
    session_id: Optional[str] = None,
    login_type: str = "web"
):
    """로그인 시도 기록"""
    if not db_status["connected"]:
        return
    
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO login_history (
                user_id, username, email, login_type, status, 
                ip_address, user_agent, failure_reason, session_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, username, email, login_type, status,
            ip_address, user_agent, failure_reason, session_id
        ))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"로그인 이력 기록 오류: {e}")

def log_audit(
    category: str,
    action: str,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    old_values: Optional[str] = None,
    new_values: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    severity: str = "info",
    status: str = "success",
    details: Optional[str] = None
):
    """시스템 감사 로그 기록"""
    if not db_status["connected"]:
        return
    
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO audit_logs (
                category, action, user_id, username, target_type, target_id,
                old_values, new_values, ip_address, user_agent, severity, status, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            category, action, user_id, username, target_type, target_id,
            old_values, new_values, ip_address, user_agent, severity, status, details
        ))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"감사 로그 기록 오류: {e}")

def get_client_info(request: Request) -> tuple[Optional[str], Optional[str]]:
    """클라이언트 정보 추출 (IP, User-Agent)"""
    try:
        # IP 주소 추출 (프록시 고려)
        ip_address = None
        if "x-forwarded-for" in request.headers:
            ip_address = request.headers["x-forwarded-for"].split(",")[0].strip()
        elif "x-real-ip" in request.headers:
            ip_address = request.headers["x-real-ip"]
        else:
            ip_address = request.client.host if request.client else None
        
        # User-Agent 추출
        user_agent = request.headers.get("user-agent")
        
        return ip_address, user_agent
    except Exception as e:
        logger.error(f"클라이언트 정보 추출 오류: {e}")
        return None, None

# 자동 백업 스케줄링 함수들
async def scheduled_daily_backup():
    """매일 자동 백업 실행"""
    try:
        logger.info("일일 자동 백업 시작")
        
        backup_result = create_database_backup(
            description="Daily automatic backup",
            include_files=True,
            compress=True
        )
        
        if backup_result["success"]:
            # 백업 성공 알림
            if BACKUP_SCHEDULE_CONFIG["notification_enabled"]:
                await send_notification_to_admins(
                    title="일일 자동 백업 완료",
                    message=f"백업 파일: {backup_result['backup_file']}",
                    type="info"
                )
            
            logger.info(f"일일 자동 백업 완료: {backup_result['backup_file']}")
            
            # 오래된 백업 정리
            if BACKUP_SCHEDULE_CONFIG["auto_cleanup"]:
                cleanup_result = cleanup_old_backups_by_retention(retention_days=BACKUP_SCHEDULE_CONFIG["retention_days"])
                if cleanup_result["cleaned_count"] > 0:
                    logger.info(f"{cleanup_result['cleaned_count']}개의 오래된 백업 파일 정리됨")
        else:
            # 백업 실패 알림
            if BACKUP_SCHEDULE_CONFIG["notification_enabled"]:
                await send_notification_to_admins(
                    title="일일 자동 백업 실패",
                    message=f"오류: {backup_result.get('error', 'Unknown error')}",
                    type="error"
                )
            logger.error(f"일일 자동 백업 실패: {backup_result.get('error')}")
            
    except Exception as e:
        logger.error(f"일일 자동 백업 중 오류: {e}")
        if BACKUP_SCHEDULE_CONFIG["notification_enabled"]:
            await send_notification_to_admins(
                title="일일 자동 백업 오류",
                message=f"시스템 오류: {str(e)}",
                type="error"
            )

async def scheduled_weekly_backup():
    """주간 자동 백업 실행 (더 상세한 백업)"""
    try:
        logger.info("주간 자동 백업 시작")
        
        backup_result = create_database_backup(
            description="Weekly comprehensive automatic backup",
            include_files=True,
            compress=True
        )
        
        if backup_result["success"]:
            # 백업 무결성 검증
            verify_result = verify_backup_integrity(backup_result['backup_file'])
            
            if verify_result["valid"]:
                # 백업 성공 및 검증 완료 알림
                if BACKUP_SCHEDULE_CONFIG["notification_enabled"]:
                    await send_notification_to_admins(
                        title="주간 자동 백업 완료",
                        message=f"백업 파일: {backup_result['backup_file']}\n검증: 통과",
                        type="success"
                    )
                logger.info(f"주간 자동 백업 및 검증 완료: {backup_result['backup_file']}")
            else:
                # 백업은 성공했지만 검증 실패
                if BACKUP_SCHEDULE_CONFIG["notification_enabled"]:
                    await send_notification_to_admins(
                        title="주간 자동 백업 검증 실패",
                        message=f"백업 파일: {backup_result['backup_file']}\n검증 오류: {verify_result.get('error')}",
                        type="warning"
                    )
                logger.warning(f"주간 자동 백업 검증 실패: {verify_result.get('error')}")
                
        else:
            # 백업 실패 알림
            if BACKUP_SCHEDULE_CONFIG["notification_enabled"]:
                await send_notification_to_admins(
                    title="주간 자동 백업 실패",
                    message=f"오류: {backup_result.get('error', 'Unknown error')}",
                    type="error"
                )
            logger.error(f"주간 자동 백업 실패: {backup_result.get('error')}")
            
    except Exception as e:
        logger.error(f"주간 자동 백업 중 오류: {e}")
        if BACKUP_SCHEDULE_CONFIG["notification_enabled"]:
            await send_notification_to_admins(
                title="주간 자동 백업 오류",
                message=f"시스템 오류: {str(e)}",
                type="error"
            )

async def send_notification_to_admins(title: str, message: str, type: str):
    """관리자들에게 알림 전송"""
    try:
        # 관리자 역할을 가진 사용자들을 조회 (현재는 user_id=1을 관리자로 가정)
        admin_ids = [1]  # 실제로는 데이터베이스에서 관리자 목록을 조회해야 함
        
        for admin_id in admin_ids:
            notification = NotificationCreate(
                title=title,
                message=message,
                type=type,
                user_id=admin_id
            )
            create_notification(notification)
            
        # WebSocket을 통해 실시간 알림도 전송
        notification_data = {
            "type": "backup_notification",
            "data": {
                "title": title,
                "message": message,
                "type": type,
                "timestamp": datetime.datetime.now().isoformat()
            }
        }
        
        # 관리자들에게 WebSocket 알림 전송
        for admin_id in admin_ids:
            await websocket_manager.send_to_user(admin_id, notification_data)
            
    except Exception as e:
        logger.error(f"관리자 알림 전송 오류: {e}")

def cleanup_old_backups_by_retention(retention_days: int = 30) -> Dict[str, Any]:
    """오래된 백업 파일 정리 (보존 기간 기반)"""
    try:
        if not os.path.exists(BACKUP_DIR):
            return {"success": True, "cleaned_count": 0, "message": "백업 디렉토리가 존재하지 않음"}
        
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
        cleaned_count = 0
        cleaned_files = []
        
        for file in os.listdir(BACKUP_DIR):
            if file.endswith("_metadata.json"):
                metadata_path = os.path.join(BACKUP_DIR, file)
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    created_at = datetime.datetime.fromisoformat(metadata.get('created_at', ''))
                    
                    # 보존 기간이 지난 백업 삭제
                    if created_at < cutoff_date:
                        backup_name = metadata.get('backup_name', '')
                        backup_file = metadata.get('backup_file', '')
                        
                        # 백업 파일 삭제
                        if backup_file:
                            backup_file_path = os.path.join(BACKUP_DIR, backup_file)
                            if os.path.exists(backup_file_path):
                                os.remove(backup_file_path)
                        
                        # 메타데이터 파일 삭제
                        os.remove(metadata_path)
                        
                        # 압축되지 않은 원본 파일들도 정리
                        for ext in ['_database.db', '_files.zip']:
                            old_file = os.path.join(BACKUP_DIR, f"{backup_name}{ext}")
                            if os.path.exists(old_file):
                                os.remove(old_file)
                        
                        cleaned_count += 1
                        cleaned_files.append(backup_file or backup_name)
                        
                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    logger.warning(f"백업 메타데이터 파싱 오류 ({file}): {e}")
                    continue
        
        return {
            "success": True, 
            "cleaned_count": cleaned_count,
            "cleaned_files": cleaned_files,
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"오래된 백업 정리 오류: {e}")
        return {"success": False, "error": str(e), "cleaned_count": 0}

def start_backup_scheduler():
    """백업 스케줄러 시작"""
    if not BACKUP_SCHEDULE_CONFIG["enabled"]:
        logger.info("백업 스케줄러가 비활성화되어 있습니다")
        return
    
    try:
        # 일일 백업 스케줄 추가
        daily_time = BACKUP_SCHEDULE_CONFIG["daily_backup_time"]
        hour, minute = daily_time.split(":")
        
        scheduler.add_job(
            scheduled_daily_backup,
            CronTrigger(hour=int(hour), minute=int(minute)),
            id='daily_backup',
            name='Daily Database Backup',
            replace_existing=True,
            max_instances=1
        )
        
        # 주간 백업 스케줄 추가  
        weekly_time = BACKUP_SCHEDULE_CONFIG["weekly_backup_time"]
        weekly_day = BACKUP_SCHEDULE_CONFIG["weekly_backup_day"]
        week_hour, week_minute = weekly_time.split(":")
        
        # 요일을 숫자로 변환 (월요일=0, 일요일=6)
        day_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        day_of_week = day_map.get(weekly_day.lower(), 6)
        
        scheduler.add_job(
            scheduled_weekly_backup,
            CronTrigger(day_of_week=day_of_week, hour=int(week_hour), minute=int(week_minute)),
            id='weekly_backup',
            name='Weekly Database Backup',
            replace_existing=True,
            max_instances=1
        )
        
        # 스케줄러 시작
        scheduler.start()
        logger.info(f"백업 스케줄러 시작됨 - 일일: {daily_time}, 주간: {weekly_day} {weekly_time}")
        
    except Exception as e:
        logger.error(f"백업 스케줄러 시작 오류: {e}")

def stop_backup_scheduler():
    """백업 스케줄러 중지"""
    try:
        if scheduler.running:
            scheduler.shutdown()
            logger.info("백업 스케줄러가 중지되었습니다")
    except Exception as e:
        logger.error(f"백업 스케줄러 중지 오류: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("LAUNCH BrandFlow FastAPI v2.0.0 시작 중...")
    await init_database()
    
    # 백업 스케줄러 시작
    start_backup_scheduler()
    
    logger.info("SUCCESS BrandFlow 서버 준비 완료!")
    
    yield
    
    # Shutdown
    logger.info("STOP BrandFlow 서버 종료 중...")
    
    # 백업 스케줄러 중지
    stop_backup_scheduler()

# API 문서화 설정
app = FastAPI(
    title="LAUNCH BrandFlow API",
    description="""
# BrandFlow Campaign Management System API

**BrandFlow**는 브랜드 캠페인을 효율적으로 관리하기 위한 종합 플랫폼입니다.

##  주요 기능

###  인증 시스템
- JWT 토큰 기반 인증
- 역할 기반 접근 제어 (관리자/사용자)
- 보안 헤더 및 미들웨어

### ANALYTICS 캠페인 관리
- 캠페인 CRUD 작업
- 예산 및 일정 관리
- 클라이언트 회사별 분류

###  발주 관리
- 구매 요청 생성 및 승인 프로세스
- 예산 관리 및 추적
- 업체별 발주 현황

### NOTIFICATIONS 알림 시스템
- 실시간 WebSocket 알림
- 이메일/SMS 알림 (향후 구현)
- 알림 히스토리 관리

###  파일 관리
- 안전한 파일 업로드
- 다양한 파일 타입 지원
- 파일 크기 및 보안 검증

### TRENDING 모니터링
- 시스템 성능 모니터링
- 사용자 활동 추적
- 실시간 상태 대시보드

## TOOLS 기술 스택
- **Backend**: FastAPI + Python 3.11
- **Database**: SQLite (개발) / PostgreSQL (프로덕션)
- **Authentication**: JWT
- **Real-time**: WebSocket
- **Deploy**: Railway Platform

## MOBILE 클라이언트 SDK
프론트엔드 개발을 위한 JavaScript/TypeScript SDK를 제공합니다.

## WEB 환경
- **개발**: http://localhost:8000
- **프로덕션**: https://brandflow-backend-production.up.railway.app

---
*Built with LOVE by BrandFlow Team*
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    terms_of_service="https://brandflow.com/terms",
    contact={
        "name": "BrandFlow API Support",
        "url": "https://brandflow.com/support",
        "email": "api-support@brandflow.com"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    },
    servers=[
        {
            "url": "http://localhost:8000",
            "description": "개발 서버"
        },
        {
            "url": "https://brandflow-backend-production.up.railway.app",
            "description": "프로덕션 서버"
        }
    ],
    openapi_tags=[
        {
            "name": " System",
            "description": "시스템 상태 및 기본 정보"
        },
        {
            "name": " Authentication",
            "description": "사용자 인증 및 권한 관리 - JWT 토큰 기반 인증 시스템"
        },
        {
            "name": " Users", 
            "description": "사용자 관리 - 프로필, 권한, 활동 내역"
        },
        {
            "name": "ANALYTICS Campaigns",
            "description": "캠페인 관리 - 생성, 수정, 삭제, 조회 및 예산 관리"
        },
        {
            "name": " Purchase Orders",
            "description": "발주 관리 - 구매 요청, 승인 프로세스, 예산 추적"
        },
        {
            "name": "NOTIFICATIONS Notifications",
            "description": "알림 시스템 - 실시간 알림, 히스토리, 설정"
        },
        {
            "name": "WEB WebSocket",
            "description": "실시간 통신 - WebSocket 연결, 브로드캐스트, 상태 관리"
        },
        {
            "name": " Files",
            "description": "파일 관리 - 업로드, 다운로드, 보안 검증"
        },
        {
            "name": " Company",
            "description": "회사 정보 - 로고, 프로필, 설정"
        },
        {
            "name": "TRENDING Monitoring",
            "description": "시스템 모니터링 - 성능, 상태, 로그"
        }
    ]
)

# 정적 파일 서빙 설정
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS 미들웨어 설정 (프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React 개발 서버
        "http://localhost:5173",  # Vite 개발 서버
        "https://brandflow-frontend.vercel.app",  # 프로덕션 프론트엔드
        "https://web-production-f12ef.up.railway.app"  # 자체 도메인
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Page-Count"]
)

# 보안 미들웨어
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=[
        "web-production-f12ef.up.railway.app",
        "localhost", 
        "127.0.0.1",
        "*.railway.app"
    ]
)

# 보안 헤더 미들웨어
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# 요청 로깅 및 통계 미들웨어  
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # 통계 업데이트
        monitoring_stats["requests_count"] += 1
        monitoring_stats["total_processing_time"] += process_time
        
        if response.status_code >= 400:
            monitoring_stats["errors_count"] += 1
        
        logger.info(
            f"{request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.3f}s"
        )
        return response
    except Exception as e:
        monitoring_stats["errors_count"] += 1
        logger.error(f"Request failed: {e}")
        raise

@app.get("/", 
         tags=[" System"],
         summary="시스템 상태 확인",
         description="""
         ## 시스템 기본 정보 조회
         
         BrandFlow API 서버의 기본 상태와 정보를 반환합니다.
         
         ### 응답 정보
         - **message**: 서비스 버전 및 환경
         - **status**: 서버 실행 상태
         - **port**: 실행 중인 포트
         - **database**: 데이터베이스 연결 상태
         """)
async def root():
    return {
        "message": "BrandFlow FastAPI v2.0.0 - Railway Test", 
        "status": "running",
        "port": os.getenv("PORT", "unknown"),
        "database": db_status["connected"]
    }

@app.get("/health",
         tags=[" System"], 
         summary="헬스 체크",
         description="""
         ## 서버 헬스 체크
         
         시스템 상태와 주요 구성 요소의 상태를 확인합니다.
         
         ### 체크 항목
         - 서버 실행 상태
         - 데이터베이스 연결 상태
         
         ### 사용 사례
         - 로드밸런서 헬스 체크
         - 모니터링 시스템 상태 확인
         - 자동화된 시스템 진단
         """)
async def health():
    return {
        "status": "healthy",
        "database": "connected" if db_status["connected"] else "disconnected"
    }

@app.get("/docs-custom",
         tags=[" System"],
         summary="커스텀 API 문서",
         description="BrandFlow 브랜드가 적용된 커스텀 Swagger UI 문서",
         response_class=HTMLResponse,
         include_in_schema=False)
async def custom_swagger_ui():
    """커스텀 스타일이 적용된 Swagger UI 반환"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>LAUNCH BrandFlow API Documentation</title>
        <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@3.52.5/swagger-ui.css" />
        <link rel="stylesheet" type="text/css" href="/static/css/swagger-ui-custom.css" />
        <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>LAUNCH</text></svg>">
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@3.52.5/swagger-ui-bundle.js"></script>
        <script src="https://unpkg.com/swagger-ui-dist@3.52.5/swagger-ui-standalone-preset.js"></script>
        <script>
            SwaggerUIBundle({
                url: '/openapi.json',
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.presets.standalone
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "StandaloneLayout",
                defaultModelsExpandDepth: 1,
                defaultModelExpandDepth: 1,
                docExpansion: "list",
                filter: true,
                showExtensions: true,
                showCommonExtensions: true,
                tryItOutEnabled: true
            });
        </script>
    </body>
    </html>
    """)

@app.get("/db/status",
         tags=[" System"],
         summary="데이터베이스 상태 확인",
         description="""
         ## 데이터베이스 연결 상태 상세 조회
         
         데이터베이스의 상세한 연결 상태와 테이블 초기화 여부를 확인합니다.
         
         ### 응답 정보
         - **connected**: 데이터베이스 연결 상태 (true/false)
         - **error**: 연결 오류 메시지 (있는 경우)
         - **tables_created**: 테이블 생성 완료 여부
         - **database_url**: 사용 중인 데이터베이스 URL
         
         ### 사용 사례
         - 시스템 초기화 상태 확인
         - 데이터베이스 마이그레이션 상태 점검
         - 장애 진단 및 디버깅
         """)
async def database_status():
    return {
        "connected": db_status["connected"],
        "error": db_status["error"],
        "tables_created": db_status["tables_created"],
        "database_url": "sqlite:///./data/brandflow.db" if db_status["connected"] else "not_configured"
    }

# 인증 의존성 함수
async def get_current_user_dependency(token: str = Depends(security)):
    """현재 사용자 정보를 가져오는 의존성 함수"""
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        user = get_user_by_email(email)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

# WebSocket 엔드포인트
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """사용자별 WebSocket 연결 엔드포인트"""
    try:
        # WebSocket 연결 수락 및 관리자에 등록
        await websocket_manager.connect(websocket, user_id)
        
        # 연결 환영 메시지 전송
        welcome_message = json.dumps({
            "type": "connection",
            "message": f"WebSocket connected for user {user_id}",
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
        await websocket.send_text(welcome_message)
        
        # 연결 유지 및 메시지 수신 대기
        while True:
            try:
                # 클라이언트로부터 메시지 수신 (ping/pong 등)
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # ping 메시지에 pong으로 응답
                if message_data.get("type") == "ping":
                    pong_message = json.dumps({
                        "type": "pong",
                        "timestamp": datetime.datetime.utcnow().isoformat()
                    })
                    await websocket.send_text(pong_message)
                
                # 기타 메시지 타입 처리 (필요시 확장 가능)
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                # JSON 파싱 오류 시 에러 메시지 전송
                error_message = json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.datetime.utcnow().isoformat()
                })
                await websocket.send_text(error_message)
            except Exception as e:
                logger.error(f"WebSocket message handling error: {e}")
                break
                
    except Exception as e:
        logger.error(f"WebSocket connection error for user {user_id}: {e}")
    finally:
        # 연결 해제 시 관리자에서 제거
        websocket_manager.disconnect(websocket, user_id)

@app.get("/api/websocket/status",
         tags=["WEB WebSocket"],
         summary="WebSocket 연결 상태 조회",
         description="""
         ## WebSocket 연결 현황 모니터링
         
         현재 활성화된 WebSocket 연결의 상태를 실시간으로 조회합니다.
         
         ###  인증 필요
         JWT 토큰을 통한 인증이 필요합니다.
         
         ### 응답 정보
         - **active_connections_by_user**: 사용자별 활성 연결 수
         - **total_connections**: 전체 활성 연결 수
         - **message**: 상태 메시지
         
         ### 사용 사례
         - 실시간 연결 모니터링
         - 서버 부하 확인
         - WebSocket 디버깅
         
         ### 예시 응답
         ```json
         {
           "active_connections_by_user": {
             "1": 2,
             "5": 1
           },
           "total_connections": 3,
           "message": "WebSocket status retrieved successfully"
         }
         ```
         """)
async def websocket_status(current_user = Depends(get_current_user_dependency)):
    return {
        "active_connections_by_user": {str(k): len(v) for k, v in websocket_manager.active_connections.items()},
        "total_connections": len(websocket_manager.all_connections),
        "message": "WebSocket status retrieved successfully"
    }

# 인증 API 엔드포인트들
@app.post("/api/auth/login-json", 
          response_model=Token,
          tags=[" Authentication"],
          summary="사용자 로그인",
          description="""
          ## JWT 토큰 기반 사용자 인증
          
          이메일과 비밀번호를 통해 사용자 인증을 수행하고 JWT 액세스 토큰을 발급합니다.
          
          ###  요청 데이터
          - **email**: 사용자 이메일 주소
          - **password**: 사용자 비밀번호
          
          ### TARGET 응답 데이터
          - **access_token**: JWT 액세스 토큰 (30분 유효)
          - **token_type**: 토큰 타입 (bearer)
          
          ###  보안
          - 비밀번호는 해시화되어 저장됨
          - JWT 토큰은 30분 후 만료
          - 역할 기반 접근 제어 지원
          
          ### LIST 사용 방법
          1. 발급받은 토큰을 `Authorization: Bearer <token>` 헤더에 포함
          2. 보호된 엔드포인트 접근 시 토큰 사용
          
          ### TOOLS 테스트 계정
          - **이메일**: test@brandflow.com  
          - **비밀번호**: test123
          - **역할**: 관리자
          
          ### WARNING 오류 코드
          - **401**: 잘못된 이메일 또는 비밀번호
          - **503**: 데이터베이스 연결 실패
          """)
async def login(login_request: LoginRequest):
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # 사용자 확인
    user = get_user_by_email(login_request.email)
    if not user or user["hashed_password"] != hash_password(login_request.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # JWT 토큰 생성
    access_token = create_access_token(
        data={"sub": user["email"], "user_id": user["id"], "role": user["role"]}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@app.post("/api/auth/register")
async def register(user_data: UserCreate):
    """사용자 회원가입"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # 이메일 중복 확인
    existing_user = get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # 사용자 생성
    if create_user(user_data):
        return {"message": "User created successfully", "email": user_data.email}
    else:
        raise HTTPException(status_code=500, detail="Failed to create user")

@app.get("/api/auth/me")
async def get_current_user(token: str = Depends(security)):
    """현재 사용자 정보 조회"""
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = get_user_by_email(email)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        return {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"]
        }
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# 비즈니스 로직 API 엔드포인트들
@app.get("/api/users")
async def get_users():
    """사용자 목록 조회"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, role, created_at FROM users")
        users = cursor.fetchall()
        conn.close()
        
        return {
            "users": [
                {
                    "id": user[0],
                    "name": user[1], 
                    "email": user[2],
                    "role": user[3],
                    "created_at": user[4]
                } for user in users
            ],
            "count": len(users)
        }
    except Exception as e:
        logger.error(f"사용자 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch users")

@app.get("/api/campaigns")
async def get_campaigns():
    """캠페인 목록 조회"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, u.name as creator_name 
            FROM campaigns c 
            LEFT JOIN users u ON c.creator_id = u.id
        """)
        campaigns = cursor.fetchall()
        conn.close()
        
        return {
            "campaigns": [
                {
                    "id": campaign[0],
                    "name": campaign[1],
                    "description": campaign[2],
                    "client_company": campaign[3],
                    "budget": campaign[4],
                    "start_date": campaign[5],
                    "end_date": campaign[6],
                    "status": campaign[7],
                    "creator_id": campaign[8],
                    "created_at": campaign[9],
                    "creator_name": campaign[10]
                } for campaign in campaigns
            ],
            "count": len(campaigns)
        }
    except Exception as e:
        logger.error(f"캠페인 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch campaigns")

@app.post("/api/campaigns",
          tags=["ANALYTICS Campaigns"],
          summary="새 캠페인 생성",
          description="""
          ## 새로운 마케팅 캠페인 생성
          
          새로운 브랜드 캠페인을 생성하고 자동으로 관련 알림을 전송합니다.
          
          ###  인증 필요
          JWT 토큰을 통한 인증이 필요합니다.
          
          ###  요청 데이터
          - **name**: 캠페인 이름 (필수)
          - **description**: 캠페인 설명 (선택)
          - **client_company**: 클라이언트 회사명 (선택)
          - **budget**: 예산 금액 (선택, 기본값: 0)
          - **start_date**: 시작일 (선택, YYYY-MM-DD 형식)
          - **end_date**: 종료일 (선택, YYYY-MM-DD 형식)
          - **status**: 상태 (선택, 기본값: "active")
          
          ### TARGET 응답 데이터
          - 생성된 캠페인의 상세 정보
          - 생성자 정보 포함
          - 생성 시간 포함
          
          ### PROCESSING 자동 동작
          - 캠페인 생성 시 자동 알림 생성
          - WebSocket을 통한 실시간 알림 전송
          - 생성자에게 확인 알림 발송
          
          ### LIST 사용 사례
          - 새로운 광고 캠페인 등록
          - 프로젝트 기반 업무 관리
          - 클라이언트별 작업 분류
          
          ### WARNING 오류 코드
          - **401**: 인증 토큰 없음 또는 무효
          - **503**: 데이터베이스 연결 실패
          """)
async def create_new_campaign(campaign_data: CampaignCreate, token: str = Depends(security)):
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰에서 사용자 정보 추출
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # 캠페인 생성
    campaign_id = create_campaign(campaign_data, user_id)
    if campaign_id:
        # 생성된 캠페인 정보 반환
        campaign = get_campaign_by_id(campaign_id)
        
        # 알림 생성
        notify_campaign_created(campaign_id, user_id, campaign_data.name)
        
        return {"message": "Campaign created successfully", "campaign": campaign}
    else:
        raise HTTPException(status_code=500, detail="Failed to create campaign")

@app.get("/api/campaigns/{campaign_id}")
async def get_campaign_detail(campaign_id: int):
    """캠페인 상세 조회"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    campaign = get_campaign_by_id(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return campaign

@app.put("/api/campaigns/{campaign_id}")
async def update_campaign_detail(
    campaign_id: int, 
    campaign_data: CampaignUpdate, 
    token: str = Depends(security)
):
    """캠페인 업데이트"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰 검증 
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # 캠페인 존재 확인
    existing_campaign = get_campaign_by_id(campaign_id)
    if not existing_campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # 권한 확인 (작성자 또는 관리자만)
    if existing_campaign["creator_id"] != user_id:
        # 관리자 권한 확인
        user = get_user_by_email(payload.get("sub"))
        if not user or user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Permission denied")
    
    # 캠페인 업데이트
    if update_campaign(campaign_id, campaign_data):
        updated_campaign = get_campaign_by_id(campaign_id)
        
        # 알림 생성
        notify_campaign_updated(campaign_id, user_id, existing_campaign["name"])
        
        return {"message": "Campaign updated successfully", "campaign": updated_campaign}
    else:
        raise HTTPException(status_code=500, detail="Failed to update campaign")

@app.delete("/api/campaigns/{campaign_id}")
async def delete_campaign_by_id(campaign_id: int, token: str = Depends(security)):
    """캠페인 삭제"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰 검증
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # 캠페인 존재 확인
    existing_campaign = get_campaign_by_id(campaign_id)
    if not existing_campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # 권한 확인 (작성자 또는 관리자만)
    if existing_campaign["creator_id"] != user_id:
        # 관리자 권한 확인
        user = get_user_by_email(payload.get("sub"))
        if not user or user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Permission denied")
    
    # 캠페인 삭제
    if delete_campaign(campaign_id):
        return {"message": "Campaign deleted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete campaign")

# 알림 API 엔드포인트들
@app.get("/api/notifications")
async def get_notifications(unread_only: bool = False, token: str = Depends(security)):
    """사용자 알림 목록 조회"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰에서 사용자 ID 추출
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    notifications = get_user_notifications(user_id, unread_only)
    unread_count = get_unread_count(user_id)
    
    return {
        "notifications": notifications,
        "count": len(notifications),
        "unread_count": unread_count
    }

@app.put("/api/notifications/{notification_id}/read")
async def mark_notification_as_read(notification_id: int, token: str = Depends(security)):
    """알림 읽음 처리"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰에서 사용자 ID 추출
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    if mark_notification_read(notification_id, user_id):
        return {"message": "Notification marked as read"}
    else:
        raise HTTPException(status_code=404, detail="Notification not found or not authorized")

@app.get("/api/notifications/unread-count")
async def get_unread_notifications_count(token: str = Depends(security)):
    """읽지 않은 알림 수 조회"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰에서 사용자 ID 추출
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    unread_count = get_unread_count(user_id)
    return {"unread_count": unread_count}

@app.post("/api/notifications")
async def create_manual_notification(notification_data: NotificationCreate, token: str = Depends(security)):
    """수동 알림 생성 (관리자용)"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰에서 사용자 정보 추출 및 관리자 권한 확인
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user = get_user_by_email(payload.get("sub"))
        if not user or user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Admin permission required")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    notification_id = create_notification(notification_data)
    if notification_id:
        return {"message": "Notification created successfully", "notification_id": notification_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to create notification")

# 파일 업로드 API 엔드포인트들
@app.post("/api/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    campaign_id: Optional[int] = None,
    description: str = "",
    token: str = Depends(security)
):
    """파일 업로드"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰에서 사용자 ID 추출
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # 파일 유효성 검사
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")
    
    if not is_allowed_file(file.filename):
        raise HTTPException(
            status_code=400, 
            detail=f"File type not allowed. Allowed types: {', '.join(ALL_ALLOWED_EXTENSIONS)}"
        )
    
    # 캠페인 존재 확인 (campaign_id가 제공된 경우)
    if campaign_id:
        campaign = get_campaign_by_id(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
    
    # 파일 업로드
    uploaded_file = save_uploaded_file(file, user_id, campaign_id, description)
    if uploaded_file:
        return {
            "message": "File uploaded successfully",
            "file": uploaded_file
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to upload file")

@app.get("/api/files")
async def get_files(campaign_id: Optional[int] = None, token: str = Depends(security)):
    """사용자 파일 목록 조회"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰에서 사용자 ID 추출
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    files = get_user_files(user_id, campaign_id)
    return {
        "files": files,
        "count": len(files)
    }

@app.get("/api/files/{file_id}")
async def get_file_info(file_id: int, token: str = Depends(security)):
    """파일 정보 조회"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰에서 사용자 ID 추출
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    file_info = get_file_by_id(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")
    
    # 권한 확인 (파일 업로더 또는 관리자만)
    if file_info["uploader_id"] != user_id:
        user = get_user_by_email(payload.get("sub"))
        if not user or user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Permission denied")
    
    return file_info

@app.get("/api/files/{file_id}/download")
async def download_file(file_id: int, token: str = Depends(security)):
    """파일 다운로드"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰에서 사용자 ID 추출
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    file_info = get_file_by_id(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")
    
    # 권한 확인 (파일 업로더 또는 관리자만)
    if file_info["uploader_id"] != user_id:
        user = get_user_by_email(payload.get("sub"))
        if not user or user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Permission denied")
    
    # 파일 존재 확인
    if not os.path.exists(file_info["file_path"]):
        raise HTTPException(status_code=404, detail="Physical file not found")
    
    return FileResponse(
        path=file_info["file_path"],
        filename=file_info["original_filename"],
        media_type=file_info["mime_type"]
    )

@app.delete("/api/files/{file_id}")
async def delete_file(file_id: int, token: str = Depends(security)):
    """파일 삭제"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰에서 사용자 ID 추출
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    file_info = get_file_by_id(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found")
    
    # 권한 확인 (파일 업로더 또는 관리자만)
    if file_info["uploader_id"] != user_id:
        user = get_user_by_email(payload.get("sub"))
        if not user or user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Permission denied")
    
    try:
        # DB에서 파일 정보 삭제
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
        conn.commit()
        conn.close()
        
        # 실제 파일 삭제
        if os.path.exists(file_info["file_path"]):
            os.remove(file_info["file_path"])
        
        return {"message": "File deleted successfully"}
    except Exception as e:
        logger.error(f"파일 삭제 오류: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete file")

# 발주관리 API 엔드포인트들
@app.post("/api/purchase-orders",
          tags=[" Purchase Orders"],
          summary="발주 요청 생성",
          description="""
          ## 새로운 발주 요청 생성
          
          캠페인에 연결된 새로운 발주 요청을 생성하고 자동으로 승인 프로세스를 시작합니다.
          
          ###  인증 필요
          JWT 토큰을 통한 인증이 필요합니다.
          
          ###  요청 데이터
          - **campaign_id**: 연결된 캠페인 ID (필수)
          - **title**: 발주 제목 (필수)
          - **description**: 발주 상세 설명 (필수)
          - **requested_amount**: 요청 금액 (필수)
          - **vendor**: 업체명 (선택, 기본값: "")
          - **category**: 카테고리 (선택, 기본값: "general")
          - **priority**: 우선순위 (선택, 기본값: "medium")
          
          ### TARGET 응답 데이터
          - 생성된 발주 요청의 상세 정보
          - 요청자 및 캠페인 정보 포함
          - 상태: "pending" (승인 대기)
          
          ### PROCESSING 자동 프로세스
          1. 발주 요청 데이터베이스 저장
          2. 캠페인 연결 및 유효성 검증
          3. 자동 알림 생성 및 전송
          4. WebSocket 실시간 알림 발송
          5. 관리자에게 승인 요청 알림
          
          ### LIST 승인 프로세스
          - 생성 시 상태: "pending"
          - 관리자 승인 후: "approved"
          - 승인 거부 시: "rejected"
          
          ### ANALYTICS 예시 요청
          ```json
          {
            "campaign_id": 1,
            "title": "광고 영상 제작",
            "description": "브랜드 홍보 영상 제작 발주",
            "requested_amount": 5000000,
            "vendor": "미디어 프로덕션",
            "category": "video_production",
            "priority": "high"
          }
          ```
          
          ### WARNING 오류 코드
          - **401**: 인증 토큰 없음 또는 무효
          - **404**: 존재하지 않는 캠페인 ID
          - **503**: 데이터베이스 연결 실패
          """)
async def create_purchase_order_request(po_data: PurchaseOrderCreate, token: str = Depends(security)):
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰에서 사용자 ID 추출
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # 캠페인 존재 확인
    campaign = get_campaign_by_id(po_data.campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # 발주요청 생성
    po_id = create_purchase_order(po_data, user_id)
    if po_id:
        # 생성된 발주요청 정보 반환
        purchase_order = get_purchase_order_by_id(po_id)
        
        # 알림 생성
        notify_purchase_order_created(po_id, po_data.campaign_id, user_id, po_data.title)
        
        return {
            "message": "Purchase order created successfully",
            "purchase_order": purchase_order
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to create purchase order")

@app.get("/api/purchase-orders")
async def get_purchase_order_list(
    campaign_id: Optional[int] = None, 
    status: Optional[str] = None, 
    token: str = Depends(security)
):
    """발주요청 목록 조회"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰 검증
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    purchase_orders = get_purchase_orders(campaign_id, status)
    
    # 일반 사용자는 자신이 요청한 발주만 볼 수 있음 (관리자는 모든 발주 조회)
    user = get_user_by_email(payload.get("sub"))
    if user and user["role"] != "admin":
        purchase_orders = [po for po in purchase_orders if po["requester_id"] == user_id]
    
    return {
        "purchase_orders": purchase_orders,
        "count": len(purchase_orders)
    }

@app.get("/api/purchase-orders/{po_id}")
async def get_purchase_order_detail(po_id: int, token: str = Depends(security)):
    """발주요청 상세 조회"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰에서 사용자 ID 추출
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    purchase_order = get_purchase_order_by_id(po_id)
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    
    # 권한 확인 (요청자 또는 관리자만)
    if purchase_order["requester_id"] != user_id:
        user = get_user_by_email(payload.get("sub"))
        if not user or user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Permission denied")
    
    return purchase_order

@app.put("/api/purchase-orders/{po_id}")
async def update_purchase_order_detail(
    po_id: int, 
    po_data: PurchaseOrderUpdate, 
    token: str = Depends(security)
):
    """발주요청 업데이트"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰에서 사용자 ID 추출
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # 발주요청 존재 확인
    existing_po = get_purchase_order_by_id(po_id)
    if not existing_po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    
    # 권한 확인 (요청자 또는 관리자만, pending 상태만 수정 가능)
    if existing_po["requester_id"] != user_id:
        user = get_user_by_email(payload.get("sub"))
        if not user or user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Permission denied")
    
    if existing_po["status"] != "pending":
        raise HTTPException(status_code=400, detail="Can only edit pending purchase orders")
    
    # 발주요청 업데이트
    if update_purchase_order(po_id, po_data):
        updated_po = get_purchase_order_by_id(po_id)
        return {
            "message": "Purchase order updated successfully",
            "purchase_order": updated_po
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to update purchase order")

@app.post("/api/purchase-orders/{po_id}/approve")
async def approve_purchase_order_request(
    po_id: int, 
    approved_amount: float,
    token: str = Depends(security)
):
    """발주요청 승인 (관리자만)"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰에서 사용자 정보 추출 및 관리자 권한 확인
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user = get_user_by_email(payload.get("sub"))
        if not user or user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Admin permission required")
        user_id = user["id"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # 발주요청 존재 확인
    existing_po = get_purchase_order_by_id(po_id)
    if not existing_po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    
    if existing_po["status"] != "pending":
        raise HTTPException(status_code=400, detail="Can only approve pending purchase orders")
    
    # 발주요청 승인
    if approve_purchase_order(po_id, user_id, approved_amount):
        # 승인 알림 생성
        notify_purchase_order_approved(
            po_id, existing_po["campaign_id"], existing_po["requester_id"], 
            existing_po["title"], approved_amount
        )
        
        updated_po = get_purchase_order_by_id(po_id)
        return {
            "message": "Purchase order approved successfully",
            "purchase_order": updated_po
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to approve purchase order")

@app.post("/api/purchase-orders/{po_id}/reject")
async def reject_purchase_order_request(
    po_id: int, 
    reason: str,
    token: str = Depends(security)
):
    """발주요청 거부 (관리자만)"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰에서 사용자 정보 추출 및 관리자 권한 확인
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user = get_user_by_email(payload.get("sub"))
        if not user or user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Admin permission required")
        user_id = user["id"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # 발주요청 존재 확인
    existing_po = get_purchase_order_by_id(po_id)
    if not existing_po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    
    if existing_po["status"] != "pending":
        raise HTTPException(status_code=400, detail="Can only reject pending purchase orders")
    
    # 발주요청 거부
    if reject_purchase_order(po_id, user_id, reason):
        # 거부 알림 생성
        notify_purchase_order_rejected(
            po_id, existing_po["campaign_id"], existing_po["requester_id"], 
            existing_po["title"], reason
        )
        
        updated_po = get_purchase_order_by_id(po_id)
        return {
            "message": "Purchase order rejected successfully",
            "purchase_order": updated_po
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to reject purchase order")

@app.get("/api/campaigns/{campaign_id}/purchase-orders")
async def get_campaign_purchase_orders(campaign_id: int, token: str = Depends(security)):
    """캠페인별 발주요청 목록 조회"""
    if not db_status["connected"]:
        raise HTTPException(status_code=503, detail="Database not available")
    
    # JWT 토큰 검증
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # 캠페인 존재 확인
    campaign = get_campaign_by_id(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    purchase_orders = get_purchase_orders(campaign_id=campaign_id)
    
    # 일반 사용자는 자신이 요청한 발주만 볼 수 있음
    user = get_user_by_email(payload.get("sub"))
    if user and user["role"] != "admin":
        purchase_orders = [po for po in purchase_orders if po["requester_id"] == user_id]
    
    return {
        "campaign": {
            "id": campaign["id"],
            "name": campaign["name"]
        },
        "purchase_orders": purchase_orders,
        "count": len(purchase_orders)
    }

# 모니터링 API 엔드포인트들
@app.get("/api/monitoring/health")
async def monitoring_health():
    """종합 헬스체크"""
    system_info = get_system_info()
    db_stats = get_database_stats()
    
    # 헬스 상태 판단
    health_status = "healthy"
    issues = []
    
    if "error" in system_info:
        health_status = "degraded"
        issues.append("System monitoring unavailable")
    else:
        if system_info.get("cpu_percent", 0) > 80:
            health_status = "degraded" 
            issues.append("High CPU usage")
        if system_info.get("memory_percent", 0) > 85:
            health_status = "degraded"
            issues.append("High memory usage")
    
    if not db_status["connected"]:
        health_status = "unhealthy" if health_status == "healthy" else "critical"
        issues.append("Database disconnected")
    
    return {
        "status": health_status,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "uptime": time.time() - monitoring_stats["start_time"],
        "database": {
            "connected": db_status["connected"],
            "tables_created": db_status["tables_created"],
            "stats": db_stats
        },
        "system": system_info,
        "issues": issues
    }

@app.get("/api/performance/stats")
async def performance_stats():
    """성능 통계 조회"""
    uptime = time.time() - monitoring_stats["start_time"]
    avg_response_time = (
        monitoring_stats["total_processing_time"] / monitoring_stats["requests_count"] 
        if monitoring_stats["requests_count"] > 0 else 0
    )
    
    system_info = get_system_info()
    
    return {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "uptime_seconds": uptime,
        "requests": {
            "total": monitoring_stats["requests_count"],
            "errors": monitoring_stats["errors_count"],
            "error_rate": (
                monitoring_stats["errors_count"] / monitoring_stats["requests_count"] * 100
                if monitoring_stats["requests_count"] > 0 else 0
            )
        },
        "response_time": {
            "total": monitoring_stats["total_processing_time"],
            "average": avg_response_time
        },
        "system": system_info,
        "database": get_database_stats()
    }

@app.get("/api/monitoring/status") 
async def monitoring_status():
    """간단한 상태 확인"""
    return {
        "api": "operational",
        "database": "operational" if db_status["connected"] else "down",
        "uptime": time.time() - monitoring_stats["start_time"],
        "requests_handled": monitoring_stats["requests_count"]
    }

# 데이터베이스 연결 시도 (안전하게)
async def init_database():
    """안전한 데이터베이스 초기화"""
    try:
        logger.info("PROCESSING 데이터베이스 연결 시도 중...")
        
        # 기본 데이터 디렉토리 생성
        os.makedirs("./data", exist_ok=True)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        # SQLite 연결 및 기본 테이블 생성
        import sqlite3
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        # 기본 테이블들 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                status TEXT DEFAULT 'active',
                last_login TIMESTAMP,
                failed_login_attempts INTEGER DEFAULT 0,
                account_locked_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 역할 및 권한 관리 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                description TEXT,
                resource TEXT NOT NULL,
                action TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS role_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE CASCADE,
                FOREIGN KEY (permission_id) REFERENCES permissions (id) ON DELETE CASCADE,
                UNIQUE(role_id, permission_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                granted_by INTEGER,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (permission_id) REFERENCES permissions (id) ON DELETE CASCADE,
                FOREIGN KEY (granted_by) REFERENCES users (id),
                UNIQUE(user_id, permission_id)
            )
        """)
        
        # 사용자 활동 로그 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                action TEXT NOT NULL,
                resource TEXT,
                resource_id TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                status TEXT DEFAULT 'success',
                error_message TEXT,
                session_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
            )
        """)
        
        # 로그인 이력 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                email TEXT,
                login_type TEXT DEFAULT 'web',
                status TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                failure_reason TEXT,
                session_id TEXT,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                logout_time TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
            )
        """)
        
        # 시스템 감사 로그 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                action TEXT NOT NULL,
                user_id INTEGER,
                username TEXT,
                target_type TEXT,
                target_id TEXT,
                old_values TEXT,
                new_values TEXT,
                ip_address TEXT,
                user_agent TEXT,
                severity TEXT DEFAULT 'info',
                status TEXT DEFAULT 'success',
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                client_company TEXT,
                budget REAL,
                start_date DATE,
                end_date DATE,
                status TEXT DEFAULT 'active',
                creator_id INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                type TEXT DEFAULT 'info',
                user_id INTEGER REFERENCES users(id),
                related_campaign_id INTEGER REFERENCES campaigns(id),
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                mime_type TEXT,
                uploader_id INTEGER REFERENCES users(id),
                related_campaign_id INTEGER REFERENCES campaigns(id),
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER REFERENCES campaigns(id),
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                requested_amount REAL NOT NULL,
                approved_amount REAL,
                vendor TEXT,
                category TEXT DEFAULT 'general',
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'pending',
                requester_id INTEGER REFERENCES users(id),
                approved_by INTEGER REFERENCES users(id),
                rejection_reason TEXT,
                requested_delivery_date DATE,
                approved_date TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        
        # 기본 테스트 사용자 생성 (존재하지 않는 경우만)
        cursor.execute("SELECT COUNT(*) FROM users WHERE email = ?", ("test@brandflow.com",))
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO users (name, email, hashed_password, role) VALUES (?, ?, ?, ?)",
                ("테스트 사용자", "test@brandflow.com", hash_password("test123"), "admin")
            )
            conn.commit()
            logger.info("SUCCESS 기본 테스트 사용자 생성: test@brandflow.com / test123")
        
        conn.close()
        
        # 기본 역할 및 권한 초기화
        await init_roles_and_permissions()
        
        db_status["connected"] = True
        db_status["tables_created"] = True
        db_status["error"] = None
        logger.info("SUCCESS 데이터베이스 연결 및 테이블 생성 완료")
        
    except Exception as e:
        db_status["connected"] = False
        db_status["tables_created"] = False
        db_status["error"] = str(e)
        logger.warning(f"WARNING 데이터베이스 초기화 실패: {e}")
        logger.info("LAUNCH 데이터베이스 없이 API 모드로 계속 진행")

# WebSocket 테스트 엔드포인트
@app.post("/api/websocket/test-broadcast")
async def test_websocket_broadcast(
    message: str = "Test notification",
    user_id: Optional[int] = None,
    current_user = Depends(get_current_user_dependency)
):
    """WebSocket 브로드캐스트 테스트 (인증 필요)"""
    try:
        test_notification = {
            "id": 999,
            "title": "WebSocket Test",
            "message": message,
            "type": "info",
            "user_id": user_id or current_user["id"],
            "related_campaign_id": None,
            "created_at": datetime.datetime.utcnow().isoformat(),
            "read": False
        }
        
        if user_id:
            await websocket_manager.broadcast_notification(test_notification, user_id)
            return {
                "message": f"Test notification sent to user {user_id}",
                "notification": test_notification
            }
        else:
            await websocket_manager.broadcast_notification(test_notification)
            return {
                "message": "Test notification broadcast to all users",
                "notification": test_notification
            }
            
    except Exception as e:
        logger.error(f"WebSocket broadcast test error: {e}")
        raise HTTPException(status_code=500, detail=f"Broadcast test failed: {str(e)}")

# 백업 및 복원 API 엔드포인트들
@app.post("/api/backup/create",
          tags=["STORAGE Backup System"],
          summary="데이터베이스 백업 생성",
          description="""
          ## 데이터베이스 및 파일 백업 생성
          
          시스템의 모든 데이터를 안전하게 백업하고 압축하여 저장합니다.
          
          ###  관리자 권한 필요
          관리자 역할의 사용자만 백업을 생성할 수 있습니다.
          
          ###  백업 옵션
          - **description**: 백업 설명 (선택)
          - **include_files**: 업로드된 파일 포함 여부 (기본값: true)
          - **compress**: 백업 파일 압축 여부 (기본값: true)
          
          ### PROCESSING 백업 프로세스
          1. 현재 데이터베이스 스냅샷 생성
          2. 업로드된 파일들 복사 (선택 시)
          3. 백업 메타데이터 생성 (테이블 목록, 파일 수, 크기)
          4. ZIP 압축 (선택 시)
          5. 오래된 백업 자동 정리 (10개 초과 시)
          
          ### ANALYTICS 백업 정보
          - 백업 파일명 (타임스탬프 기반)
          - 데이터베이스 크기 및 테이블 목록
          - 포함된 파일 수 및 전체 크기
          - 생성 시간 및 설명
          
          ### WARNING 주의사항
          - 백업 중 시스템 성능에 일시적 영향 가능
          - 큰 파일이 많을 경우 백업 시간 소요
          - 최대 10개 백업 파일 보관 (오래된 것 자동 삭제)
          """)
async def create_backup(
    backup_request: BackupRequest,
    current_user = Depends(require_permission("backup.create"))
):
    
    try:
        backup_info = create_database_backup(
            description=backup_request.description,
            include_files=backup_request.include_files,
            compress=backup_request.compress
        )
        
        if "error" in backup_info:
            raise HTTPException(status_code=500, detail=backup_info["error"])
        
        # 백업 생성 알림
        notification = NotificationCreate(
            title="데이터베이스 백업 생성",
            message=f"백업 '{backup_info['backup_file']}'이(가) 성공적으로 생성되었습니다. (크기: {backup_info['total_size']:,} bytes)",
            type="success",
            user_id=current_user["id"]
        )
        create_notification(notification)
        
        return {
            "message": "백업이 성공적으로 생성되었습니다",
            "backup": backup_info
        }
        
    except Exception as e:
        logger.error(f"백업 생성 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"백업 생성 실패: {str(e)}")

@app.get("/api/backup/list",
         tags=["STORAGE Backup System"],
         summary="백업 목록 조회",
         description="""
         ## 사용 가능한 백업 목록 조회
         
         생성된 모든 백업의 상세 정보를 조회합니다.
         
         ###  관리자 권한 필요
         관리자 역할의 사용자만 백업 목록을 조회할 수 있습니다.
         
         ### ANALYTICS 백업 정보
         - **backup_name**: 백업 고유 이름
         - **backup_file**: 실제 백업 파일명
         - **created_at**: 생성 시간
         - **description**: 백업 설명
         - **total_size**: 전체 크기 (bytes)
         - **database_size**: 데이터베이스 크기
         - **files_count**: 포함된 파일 수
         - **tables_backed_up**: 백업된 테이블 목록
         - **file_exists**: 파일 존재 여부
         
         ### LIST 정렬 및 필터링
         - 생성일 기준 최신순 정렬
         - 존재하지 않는 백업 파일 표시
         - 메타데이터 오류 자동 필터링
         """)
async def list_backups(current_user = Depends(require_permission("backup.read"))):
    
    try:
        backups = list_available_backups()
        return {
            "message": "백업 목록 조회 완료",
            "backups": backups,
            "total_backups": len(backups)
        }
    except Exception as e:
        logger.error(f"백업 목록 조회 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"백업 목록 조회 실패: {str(e)}")

@app.post("/api/backup/restore",
          tags=["STORAGE Backup System"],
          summary="데이터베이스 백업 복원",
          description="""
          ## 데이터베이스 백업 복원
          
          선택한 백업에서 데이터베이스와 파일을 복원합니다.
          
          ###  관리자 권한 필요
          관리자 역할의 사용자만 백업을 복원할 수 있습니다.
          
          ### WARNING 매우 중요한 작업
          - **현재 데이터는 완전히 교체됩니다**
          - 복원 전 현재 상태의 자동 백업 생성
          - 복원 후 되돌릴 수 없음 (자동 백업으로만 복구 가능)
          
          ###  복원 옵션
          - **backup_filename**: 복원할 백업 파일명 (필수)
          - **confirm_restore**: 복원 확인 (true로 설정 필요)
          
          ### PROCESSING 복원 프로세스
          1. 백업 파일 존재 및 무결성 확인
          2. 현재 데이터베이스 자동 백업 생성
          3. 백업 파일 압축 해제 (ZIP인 경우)
          4. 데이터베이스 교체
          5. 파일 복원 (포함된 경우)
          6. 복원 완료 알림
          
          ### ANALYTICS 복원 정보
          - 복원된 백업 정보
          - 복원 전 자동 백업 파일
          - 복원된 파일 및 데이터베이스 정보
          
          ### FAILED 주의사항
          - **데이터 손실 위험이 높은 작업입니다**
          - 복원 중 시스템 접근 제한
          - 실패 시 시스템 복구 필요할 수 있음
          """)
async def restore_backup(
    restore_request: RestoreRequest,
    current_user = Depends(require_permission("backup.restore"))
):
    
    # 복원 확인 필수
    if not restore_request.confirm_restore:
        raise HTTPException(status_code=400, detail="복원 확인이 필요합니다. confirm_restore를 true로 설정해주세요.")
    
    try:
        restore_info = restore_database_backup(restore_request.backup_filename)
        
        if not restore_info.get("success"):
            raise HTTPException(status_code=400, detail=restore_info.get("error", "복원에 실패했습니다"))
        
        # 복원 완료 알림
        notification = NotificationCreate(
            title="데이터베이스 복원 완료",
            message=f"백업 '{restore_request.backup_filename}'에서 데이터가 성공적으로 복원되었습니다.",
            type="info",
            user_id=current_user["id"]
        )
        create_notification(notification)
        
        return {
            "message": "백업이 성공적으로 복원되었습니다",
            "restore_info": restore_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"백업 복원 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"백업 복원 실패: {str(e)}")

@app.get("/api/backup/{backup_filename}/verify",
         tags=["STORAGE Backup System"],
         summary="백업 파일 무결성 검증",
         description="""
         ## 백업 파일 무결성 검증
         
         백업 파일의 상태와 무결성을 상세히 검증합니다.
         
         ###  관리자 권한 필요
         관리자 역할의 사용자만 백업을 검증할 수 있습니다.
         
         ### SEARCH 검증 항목
         - **파일 존재 여부**: 백업 파일이 실제로 존재하는지 확인
         - **파일 읽기 가능**: 파일이 손상되지 않고 읽을 수 있는지 확인
         - **압축 파일 무결성**: ZIP 파일인 경우 압축 상태 검증
         - **데이터베이스 유효성**: 백업된 데이터베이스 파일 존재 확인
         - **메타데이터 일치**: 저장된 메타데이터와 실제 파일 크기 비교
         
         ### ANALYTICS 검증 결과
         - **valid**: 전체 무결성 검증 결과 (true/false)
         - **checks**: 개별 검증 항목별 결과
         - **details**: 상세 검증 정보
         
         ### LIST 검증 세부사항
         - 실제 파일 크기 vs 메타데이터 크기
         - ZIP 파일 내부 구조 (압축된 경우)
         - 데이터베이스 파일 유효성
         - 메타데이터 파일 존재 및 형식
         
         ###  오류 탐지
         - 손상된 백업 파일 식별
         - 불완전한 백업 탐지
         - 메타데이터 불일치 발견
         """)
async def verify_backup(
    backup_filename: str,
    current_user = Depends(require_permission("backup.read"))
):
    
    try:
        verification_result = verify_backup_integrity(backup_filename)
        
        return {
            "message": "백업 검증 완료",
            "verification": verification_result
        }
        
    except Exception as e:
        logger.error(f"백업 검증 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"백업 검증 실패: {str(e)}")

@app.delete("/api/backup/{backup_filename}",
            tags=["STORAGE Backup System"], 
            summary="백업 파일 삭제",
            description="""
            ## 백업 파일 삭제
            
            지정된 백업 파일과 메타데이터를 완전히 삭제합니다.
            
            ###  관리자 권한 필요
            관리자 역할의 사용자만 백업을 삭제할 수 있습니다.
            
            ### WARNING 주의사항
            - **삭제된 백업은 복구할 수 없습니다**
            - 백업 파일과 메타데이터가 모두 삭제됩니다
            - 삭제 전 확인 없이 즉시 실행됩니다
            
            ### PROCESSING 삭제 프로세스
            1. 백업 파일 존재 확인
            2. 백업 파일 삭제 (.zip 또는 디렉토리)
            3. 메타데이터 파일 삭제 (_metadata.json)
            4. 삭제 완료 알림 생성
            
            ### ANALYTICS 삭제 정보
            - 삭제된 백업 파일명
            - 삭제된 파일 크기
            - 삭제 시간
            """)
async def delete_backup(
    backup_filename: str,
    current_user = Depends(require_permission("backup.delete"))
):
    
    try:
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        if not os.path.exists(backup_path):
            raise HTTPException(status_code=404, detail="백업 파일을 찾을 수 없습니다")
        
        # 파일 크기 확인 (삭제 전)
        file_size = os.path.getsize(backup_path)
        
        # 백업 파일 삭제
        os.remove(backup_path)
        
        # 메타데이터 파일 삭제
        metadata_name = backup_filename.replace('.zip', '_metadata.json')
        metadata_path = os.path.join(BACKUP_DIR, metadata_name)
        if os.path.exists(metadata_path):
            os.remove(metadata_path)
        
        # 삭제 완료 알림
        notification = NotificationCreate(
            title="백업 파일 삭제",
            message=f"백업 '{backup_filename}'이(가) 삭제되었습니다. (크기: {file_size:,} bytes)",
            type="info",
            user_id=current_user["id"]
        )
        create_notification(notification)
        
        logger.info(f"백업 파일 삭제 완료: {backup_filename}")
        return {
            "message": "백업 파일이 성공적으로 삭제되었습니다",
            "deleted_backup": backup_filename,
            "deleted_size": file_size
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"백업 삭제 API 오류: {e}")
        raise HTTPException(status_code=500, detail=f"백업 삭제 실패: {str(e)}")

# 백업 스케줄 관리 API 엔드포인트
@app.get("/api/backup/schedule/status",
         tags=["STORAGE Backup System"], 
         summary="백업 스케줄 상태 조회",
         description="""
         ## 백업 스케줄 상태 조회
         
         현재 설정된 백업 스케줄과 스케줄러 상태를 확인합니다.
         
         ###  관리자 권한 필요
         관리자 역할의 사용자만 스케줄 상태를 조회할 수 있습니다.
         
         ### ANALYTICS 제공 정보
         - 스케줄러 실행 상태 (활성/비활성)
         - 일일 백업 스케줄 설정
         - 주간 백업 스케줄 설정
         - 자동 정리 설정
         - 알림 설정
         - 다음 예정 백업 시간
         
         ###  스케줄 시간
         - 일일 백업: 매일 설정된 시간에 자동 실행
         - 주간 백업: 매주 설정된 요일과 시간에 자동 실행
         """)
async def get_backup_schedule_status(
    current_user = Depends(require_permission("backup.schedule"))
):
    
    try:
        # 스케줄러 상태 확인
        scheduler_running = scheduler.running if hasattr(scheduler, 'running') else False
        
        # 예정된 작업 목록
        scheduled_jobs = []
        if scheduler_running:
            for job in scheduler.get_jobs():
                scheduled_jobs.append({
                    "job_id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger)
                })
        
        return {
            "scheduler_status": {
                "running": scheduler_running,
                "enabled": BACKUP_SCHEDULE_CONFIG["enabled"]
            },
            "schedule_config": BACKUP_SCHEDULE_CONFIG,
            "scheduled_jobs": scheduled_jobs,
            "backup_directory": BACKUP_DIR,
            "max_backup_count": MAX_BACKUP_COUNT
        }
        
    except Exception as e:
        logger.error(f"백업 스케줄 상태 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"스케줄 상태 조회 실패: {str(e)}")

@app.post("/api/backup/schedule/trigger-daily",
          tags=["STORAGE Backup System"], 
          summary="일일 백업 수동 실행",
          description="""
          ## 일일 백업 수동 실행
          
          예정된 스케줄과 별도로 일일 백업을 즉시 실행합니다.
          
          ###  관리자 권한 필요
          관리자 역할의 사용자만 수동 백업을 실행할 수 있습니다.
          
          ### PROCESSING 실행 프로세스
          1. 즉시 데이터베이스 백업 생성
          2. 파일 압축 및 메타데이터 생성
          3. 백업 완료 알림 전송
          4. 오래된 백업 자동 정리 (설정된 경우)
          
          ### ANALYTICS 실행 결과
          - 백업 성공/실패 상태
          - 생성된 백업 파일 정보
          - 실행 시간 및 소요 시간
          - 정리된 오래된 백업 수
          
          ### WARNING 주의사항
          - 기존 스케줄된 백업과 독립적으로 실행됩니다
          - 대용량 데이터베이스의 경우 시간이 소요될 수 있습니다
          """)
async def trigger_daily_backup(
    current_user = Depends(require_permission("backup.schedule"))
):
    
    try:
        start_time = datetime.datetime.now()
        logger.info(f"관리자 {current_user['username']}이 수동 일일 백업을 실행했습니다")
        
        # 일일 백업 실행
        await scheduled_daily_backup()
        
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        return {
            "message": "일일 백업이 수동으로 실행되었습니다",
            "triggered_by": current_user["username"],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "type": "manual_daily_backup"
        }
        
    except Exception as e:
        logger.error(f"수동 일일 백업 실행 오류: {e}")
        raise HTTPException(status_code=500, detail=f"일일 백업 실행 실패: {str(e)}")

@app.post("/api/backup/schedule/trigger-weekly",
          tags=["STORAGE Backup System"], 
          summary="주간 백업 수동 실행",
          description="""
          ## 주간 백업 수동 실행
          
          예정된 스케줄과 별도로 주간 백업을 즉시 실행합니다.
          
          ###  관리자 권한 필요
          관리자 역할의 사용자만 수동 백업을 실행할 수 있습니다.
          
          ### PROCESSING 실행 프로세스
          1. 즉시 데이터베이스 백업 생성
          2. 파일 압축 및 메타데이터 생성
          3. 백업 무결성 검증 실행
          4. 백업 완료 알림 전송
          
          ### ANALYTICS 실행 결과
          - 백업 성공/실패 상태
          - 생성된 백업 파일 정보
          - 무결성 검증 결과
          - 실행 시간 및 소요 시간
          
          ### SEARCH 검증 기능
          - 백업 파일 읽기 가능성 확인
          - ZIP 파일 무결성 검사
          - 데이터베이스 파일 유효성 확인
          - 메타데이터 일치성 검증
          
          ### WARNING 주의사항
          - 기존 스케줄된 백업과 독립적으로 실행됩니다
          - 검증 과정 때문에 일일 백업보다 시간이 소요됩니다
          """)
async def trigger_weekly_backup(
    current_user = Depends(require_permission("backup.schedule"))
):
    
    try:
        start_time = datetime.datetime.now()
        logger.info(f"관리자 {current_user['username']}이 수동 주간 백업을 실행했습니다")
        
        # 주간 백업 실행
        await scheduled_weekly_backup()
        
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        return {
            "message": "주간 백업이 수동으로 실행되었습니다",
            "triggered_by": current_user["username"],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "type": "manual_weekly_backup",
            "verification_included": True
        }
        
    except Exception as e:
        logger.error(f"수동 주간 백업 실행 오류: {e}")
        raise HTTPException(status_code=500, detail=f"주간 백업 실행 실패: {str(e)}")

@app.post("/api/backup/schedule/cleanup",
          tags=["STORAGE Backup System"], 
          summary="오래된 백업 수동 정리",
          description="""
          ## 오래된 백업 수동 정리
          
          설정된 보존 기간보다 오래된 백업을 수동으로 정리합니다.
          
          ###  관리자 권한 필요
          관리자 역할의 사용자만 백업 정리를 실행할 수 있습니다.
          
          ### PROCESSING 정리 프로세스
          1. 백업 디렉토리 스캔
          2. 각 백업의 생성 날짜 확인
          3. 보존 기간 초과 백업 식별
          4. 백업 파일 및 메타데이터 삭제
          5. 정리 결과 보고
          
          ### ANALYTICS 정리 기준
          - 기본 보존 기간: 30일
          - 메타데이터 기반 생성일 확인
          - ZIP 파일 및 관련 파일 모두 삭제
          
          ###  정리 범위
          - 만료된 백업 파일 (.zip)
          - 관련 메타데이터 파일 (_metadata.json)
          - 압축되지 않은 백업 파일들
          
          ### WARNING 주의사항
          - **삭제된 백업은 복구할 수 없습니다**
          - 현재 실행 중인 백업은 정리되지 않습니다
          - 최소한의 최신 백업은 보존됩니다
          """)
async def manual_backup_cleanup(
    retention_days: Optional[int] = BACKUP_SCHEDULE_CONFIG["retention_days"],
    current_user = Depends(require_permission("backup.delete"))
):
    
    try:
        start_time = datetime.datetime.now()
        logger.info(f"관리자 {current_user['username']}이 수동 백업 정리를 실행했습니다 (보존 기간: {retention_days}일)")
        
        # 백업 정리 실행
        cleanup_result = cleanup_old_backups_by_retention(retention_days=retention_days)
        
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        return {
            "message": f"{cleanup_result['cleaned_count']}개의 백업이 정리되었습니다",
            "triggered_by": current_user["username"],
            "retention_days": retention_days,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "cleanup_result": cleanup_result
        }
        
    except Exception as e:
        logger.error(f"수동 백업 정리 실행 오류: {e}")
        raise HTTPException(status_code=500, detail=f"백업 정리 실행 실패: {str(e)}")

# 권한 관리 API 엔드포인트
@app.get("/api/admin/roles",
         tags=[" User Management"], 
         summary="역할 목록 조회",
         description="""
         ## 역할 목록 조회
         
         시스템에 등록된 모든 역할을 조회합니다.
         
         ###  필요 권한
         - `user.read`: 사용자 관리 권한
         
         ### ANALYTICS 제공 정보
         - 역할 ID, 이름, 표시명
         - 역할 설명 및 활성 상태
         - 각 역할에 할당된 권한 목록
         - 역할별 사용자 수
         """)
async def get_all_roles(current_user = Depends(require_permission("user.read"))):
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        # 역할 목록과 각 역할의 사용자 수 조회
        cursor.execute("""
            SELECT r.id, r.name, r.display_name, r.description, r.is_active, r.created_at,
                   COUNT(u.id) as user_count
            FROM roles r
            LEFT JOIN users u ON r.name = u.role
            GROUP BY r.id, r.name, r.display_name, r.description, r.is_active, r.created_at
            ORDER BY r.name
        """)
        
        roles = []
        for row in cursor.fetchall():
            role_id, name, display_name, description, is_active, created_at, user_count = row
            
            # 각 역할의 권한 목록 조회
            cursor.execute("""
                SELECT p.name, p.display_name, p.description, p.resource, p.action
                FROM role_permissions rp
                JOIN permissions p ON rp.permission_id = p.id
                WHERE rp.role_id = ?
                ORDER BY p.resource, p.action
            """, (role_id,))
            
            permissions = [
                {
                    "name": perm_name,
                    "display_name": perm_display_name,
                    "description": perm_description,
                    "resource": resource,
                    "action": action
                }
                for perm_name, perm_display_name, perm_description, resource, action in cursor.fetchall()
            ]
            
            roles.append({
                "id": role_id,
                "name": name,
                "display_name": display_name,
                "description": description,
                "is_active": bool(is_active),
                "created_at": created_at,
                "user_count": user_count,
                "permissions": permissions
            })
        
        conn.close()
        return {"roles": roles}
        
    except Exception as e:
        logger.error(f"역할 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"역할 목록 조회 실패: {str(e)}")

@app.get("/api/admin/permissions",
         tags=[" User Management"], 
         summary="권한 목록 조회",
         description="""
         ## 권한 목록 조회
         
         시스템에 등록된 모든 권한을 조회합니다.
         
         ###  필요 권한
         - `user.read`: 사용자 관리 권한
         
         ### ANALYTICS 제공 정보
         - 권한 ID, 이름, 표시명
         - 권한 설명 및 리소스/액션
         - 각 권한을 가진 역할 목록
         """)
async def get_all_permissions(current_user = Depends(require_permission("user.read"))):
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        # 권한 목록 조회
        cursor.execute("""
            SELECT id, name, display_name, description, resource, action, created_at
            FROM permissions
            ORDER BY resource, action
        """)
        
        permissions = []
        for row in cursor.fetchall():
            perm_id, name, display_name, description, resource, action, created_at = row
            
            # 각 권한을 가진 역할 목록 조회
            cursor.execute("""
                SELECT r.name, r.display_name
                FROM role_permissions rp
                JOIN roles r ON rp.role_id = r.id
                WHERE rp.permission_id = ? AND r.is_active = 1
                ORDER BY r.name
            """, (perm_id,))
            
            roles = [
                {"name": role_name, "display_name": role_display_name}
                for role_name, role_display_name in cursor.fetchall()
            ]
            
            permissions.append({
                "id": perm_id,
                "name": name,
                "display_name": display_name,
                "description": description,
                "resource": resource,
                "action": action,
                "created_at": created_at,
                "roles": roles
            })
        
        conn.close()
        return {"permissions": permissions}
        
    except Exception as e:
        logger.error(f"권한 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"권한 목록 조회 실패: {str(e)}")

@app.get("/api/admin/users/{user_id}/permissions",
         tags=[" User Management"], 
         summary="사용자 권한 조회",
         description="""
         ## 사용자 권한 조회
         
         특정 사용자의 모든 권한을 조회합니다.
         
         ###  필요 권한
         - `user.read`: 사용자 관리 권한
         
         ### ANALYTICS 제공 정보
         - 역할을 통해 부여된 권한
         - 개별적으로 부여된 권한
         - 권한별 만료 날짜
         - 권한 부여자 정보
         """)
async def get_user_permissions_detail(
    user_id: int,
    current_user = Depends(require_permission("user.read"))
):
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        # 사용자 정보 확인
        cursor.execute("SELECT id, name, email, role FROM users WHERE id = ?", (user_id,))
        user_data = cursor.fetchone()
        if not user_data:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        user_info = {
            "id": user_data[0],
            "name": user_data[1],
            "email": user_data[2],
            "role": user_data[3]
        }
        
        # 역할을 통한 권한 조회
        cursor.execute("""
            SELECT p.name, p.display_name, p.description, p.resource, p.action,
                   'role' as source, r.display_name as source_name
            FROM users u
            JOIN roles r ON u.role = r.name
            JOIN role_permissions rp ON r.id = rp.role_id
            JOIN permissions p ON rp.permission_id = p.id
            WHERE u.id = ? AND r.is_active = 1
            ORDER BY p.resource, p.action
        """, (user_id,))
        
        role_permissions = [
            {
                "name": row[0],
                "display_name": row[1],
                "description": row[2],
                "resource": row[3],
                "action": row[4],
                "source": row[5],
                "source_name": row[6],
                "expires_at": None
            }
            for row in cursor.fetchall()
        ]
        
        # 개별 권한 조회
        cursor.execute("""
            SELECT p.name, p.display_name, p.description, p.resource, p.action,
                   up.granted_at, up.expires_at, u2.name as granted_by_name
            FROM user_permissions up
            JOIN permissions p ON up.permission_id = p.id
            LEFT JOIN users u2 ON up.granted_by = u2.id
            WHERE up.user_id = ?
            AND (up.expires_at IS NULL OR up.expires_at > CURRENT_TIMESTAMP)
            ORDER BY p.resource, p.action
        """, (user_id,))
        
        individual_permissions = [
            {
                "name": row[0],
                "display_name": row[1],
                "description": row[2],
                "resource": row[3],
                "action": row[4],
                "source": "individual",
                "source_name": f"개별 권한 (부여자: {row[7] or 'Unknown'})",
                "granted_at": row[5],
                "expires_at": row[6]
            }
            for row in cursor.fetchall()
        ]
        
        # 모든 권한을 합쳐서 리소스별로 그룹화
        all_permissions = role_permissions + individual_permissions
        
        # 리소스별 그룹화
        permissions_by_resource = {}
        for perm in all_permissions:
            resource = perm["resource"]
            if resource not in permissions_by_resource:
                permissions_by_resource[resource] = []
            permissions_by_resource[resource].append(perm)
        
        conn.close()
        
        return {
            "user": user_info,
            "permissions_by_resource": permissions_by_resource,
            "total_permissions": len(all_permissions),
            "role_permissions_count": len(role_permissions),
            "individual_permissions_count": len(individual_permissions)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"사용자 권한 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"사용자 권한 조회 실패: {str(e)}")

@app.put("/api/admin/users/{user_id}/role",
         tags=[" User Management"], 
         summary="사용자 역할 변경",
         description="""
         ## 사용자 역할 변경
         
         특정 사용자의 역할을 변경합니다.
         
         ###  필요 권한
         - `user.manage_roles`: 사용자 역할 관리 권한
         
         ### LIST 변경 프로세스
         1. 사용자 존재 확인
         2. 새 역할 유효성 확인
         3. 역할 변경 실행
         4. 변경 알림 생성
         
         ### WARNING 주의사항
         - super_admin 역할은 super_admin만 부여 가능
         - 자신의 역할은 변경할 수 없음
         """)
async def update_user_role(
    user_id: int,
    role_data: UserRoleUpdate,
    current_user = Depends(require_permission("user.manage_roles"))
):
    try:
        # 자신의 역할은 변경할 수 없음
        if current_user["id"] == user_id:
            raise HTTPException(status_code=400, detail="자신의 역할은 변경할 수 없습니다")
        
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        # 사용자 존재 확인
        cursor.execute("SELECT id, name, email, role FROM users WHERE id = ?", (user_id,))
        user_data = cursor.fetchone()
        if not user_data:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        old_role = user_data[3]
        
        # super_admin 역할 부여는 super_admin만 가능
        if role_data.role == "super_admin" and current_user["role"] != "super_admin":
            raise HTTPException(status_code=403, detail="super_admin 역할은 최고 관리자만 부여할 수 있습니다")
        
        # 새 역할 존재 확인
        cursor.execute("SELECT id, display_name FROM roles WHERE name = ? AND is_active = 1", (role_data.role,))
        role_result = cursor.fetchone()
        if not role_result:
            raise HTTPException(status_code=400, detail="유효하지 않은 역할입니다")
        
        role_display_name = role_result[1]
        
        # 역할 업데이트
        cursor.execute("""
            UPDATE users 
            SET role = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (role_data.role, user_id))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=400, detail="역할 변경에 실패했습니다")
        
        conn.commit()
        conn.close()
        
        # 변경 알림 생성
        notification = NotificationCreate(
            title="사용자 역할 변경",
            message=f"{user_data[1]}님의 역할이 '{old_role}'에서 '{role_display_name}'로 변경되었습니다.",
            type="info",
            user_id=user_id
        )
        create_notification(notification)
        
        logger.info(f"사용자 {user_data[1]}의 역할이 {old_role}에서 {role_data.role}로 변경됨 (변경자: {current_user['username']})")
        
        return {
            "message": "사용자 역할이 성공적으로 변경되었습니다",
            "user_id": user_id,
            "user_name": user_data[1],
            "old_role": old_role,
            "new_role": role_data.role,
            "new_role_display_name": role_display_name,
            "changed_by": current_user["username"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"사용자 역할 변경 오류: {e}")
        raise HTTPException(status_code=500, detail=f"사용자 역할 변경 실패: {str(e)}")

@app.post("/api/admin/users/{user_id}/permissions",
          tags=[" User Management"], 
          summary="사용자 개별 권한 부여",
          description="""
          ## 사용자 개별 권한 부여
          
          특정 사용자에게 개별 권한을 부여합니다.
          
          ###  필요 권한
          - `user.manage_roles`: 사용자 역할 관리 권한
          
          ### LIST 부여 프로세스
          1. 사용자 및 권한 존재 확인
          2. 기존 권한 중복 확인
          3. 권한 부여 실행
          4. 부여 알림 생성
          
          ###  만료 날짜
          - 만료 날짜 미설정 시 영구 권한
          - ISO 8601 형식 지원 (예: 2024-12-31T23:59:59)
          """)
async def grant_user_permission(
    user_id: int,
    permission_data: UserPermissionGrant,
    current_user = Depends(require_permission("user.manage_roles"))
):
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        # 사용자 존재 확인
        cursor.execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,))
        user_data = cursor.fetchone()
        if not user_data:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
        
        # 권한 존재 확인
        cursor.execute("SELECT id, display_name FROM permissions WHERE name = ?", (permission_data.permission_name,))
        perm_result = cursor.fetchone()
        if not perm_result:
            raise HTTPException(status_code=400, detail="유효하지 않은 권한입니다")
        
        permission_id, permission_display_name = perm_result
        
        # 기존 권한 확인 (만료되지 않은 것)
        cursor.execute("""
            SELECT id FROM user_permissions 
            WHERE user_id = ? AND permission_id = ?
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        """, (user_id, permission_id))
        
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="사용자가 이미 해당 권한을 가지고 있습니다")
        
        # 만료 날짜 처리
        expires_at = None
        if permission_data.expires_at:
            try:
                expires_at = permission_data.expires_at
                # 날짜 형식 검증
                from datetime import datetime
                datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="만료 날짜 형식이 올바르지 않습니다 (ISO 8601 형식 사용)")
        
        # 권한 부여
        cursor.execute("""
            INSERT INTO user_permissions (user_id, permission_id, granted_by, expires_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, permission_id, current_user["id"], expires_at))
        
        conn.commit()
        conn.close()
        
        # 부여 알림 생성
        expires_msg = f" (만료: {expires_at})" if expires_at else " (영구)"
        notification = NotificationCreate(
            title="개별 권한 부여",
            message=f"'{permission_display_name}' 권한이 부여되었습니다{expires_msg}",
            type="info",
            user_id=user_id
        )
        create_notification(notification)
        
        logger.info(f"사용자 {user_data[1]}에게 권한 {permission_data.permission_name} 부여됨 (부여자: {current_user['username']})")
        
        return {
            "message": "사용자에게 권한이 성공적으로 부여되었습니다",
            "user_id": user_id,
            "user_name": user_data[1],
            "permission_name": permission_data.permission_name,
            "permission_display_name": permission_display_name,
            "expires_at": expires_at,
            "granted_by": current_user["username"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"사용자 권한 부여 오류: {e}")
        raise HTTPException(status_code=500, detail=f"사용자 권한 부여 실패: {str(e)}")

@app.get("/api/admin/users",
         tags=[" User Management"], 
         summary="사용자 목록 조회",
         description="""
         ## 사용자 목록 조회
         
         시스템에 등록된 모든 사용자를 조회합니다.
         
         ###  필요 권한
         - `user.read`: 사용자 관리 권한
         
         ### ANALYTICS 제공 정보
         - 사용자 기본 정보 (ID, 이름, 이메일)
         - 역할 및 계정 상태
         - 마지막 로그인 시간
         - 실패한 로그인 시도 수
         - 계정 잠금 상태
         """)
async def get_all_users(current_user = Depends(require_permission("user.read"))):
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.role, u.status, u.last_login,
                   u.failed_login_attempts, u.account_locked_until, u.created_at,
                   r.display_name as role_display_name
            FROM users u
            LEFT JOIN roles r ON u.role = r.name
            ORDER BY u.created_at DESC
        """)
        
        users = []
        for row in cursor.fetchall():
            user_id, name, email, role, status, last_login, failed_attempts, locked_until, created_at, role_display = row
            
            users.append({
                "id": user_id,
                "name": name,
                "email": email,
                "role": role,
                "role_display_name": role_display or role,
                "status": status,
                "last_login": last_login,
                "failed_login_attempts": failed_attempts,
                "account_locked_until": locked_until,
                "created_at": created_at,
                "is_locked": locked_until is not None and locked_until > datetime.datetime.now().isoformat()
            })
        
        conn.close()
        return {"users": users, "total_count": len(users)}
        
    except Exception as e:
        logger.error(f"사용자 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"사용자 목록 조회 실패: {str(e)}")

# 활동 로그 및 감사 추적 API 엔드포인트
@app.get("/api/admin/logs/activity",
         tags=["ANALYTICS Audit & Logs"], 
         summary="사용자 활동 로그 조회",
         description="""
         ## 사용자 활동 로그 조회
         
         시스템의 사용자 활동 로그를 조회합니다.
         
         ###  필요 권한
         - `system.logs`: 시스템 로그 조회 권한
         
         ### ANALYTICS 조회 옵션
         - **user_id**: 특정 사용자의 로그만 조회
         - **action**: 특정 액션의 로그만 조회
         - **resource**: 특정 리소스의 로그만 조회
         - **status**: 성공/실패 상태별 조회
         - **start_date**: 조회 시작 날짜
         - **end_date**: 조회 종료 날짜
         - **limit**: 최대 조회 개수 (기본: 100)
         
         ### LIST 제공 정보
         - 사용자 정보 (ID, 이름)
         - 액션 및 리소스 정보
         - 상세 내용 및 상태
         - IP 주소 및 User-Agent
         - 타임스탬프
         """)
async def get_activity_logs(
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    resource: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user = Depends(require_permission("system.logs"))
):
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        # 기본 쿼리
        query = """
            SELECT id, user_id, username, action, resource, resource_id, details,
                   ip_address, user_agent, status, error_message, session_id, created_at
            FROM activity_logs
            WHERE 1=1
        """
        params = []
        
        # 필터 조건 추가
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if action:
            query += " AND action LIKE ?"
            params.append(f"%{action}%")
        
        if resource:
            query += " AND resource = ?"
            params.append(resource)
            
        if status:
            query += " AND status = ?"
            params.append(status)
            
        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date)
            
        if end_date:
            query += " AND created_at <= ?"
            params.append(end_date)
        
        # 정렬 및 제한
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        logs = []
        
        for row in cursor.fetchall():
            logs.append({
                "id": row[0],
                "user_id": row[1],
                "username": row[2],
                "action": row[3],
                "resource": row[4],
                "resource_id": row[5],
                "details": row[6],
                "ip_address": row[7],
                "user_agent": row[8],
                "status": row[9],
                "error_message": row[10],
                "session_id": row[11],
                "created_at": row[12]
            })
        
        # 총 개수 조회
        count_query = query.replace(
            "SELECT id, user_id, username, action, resource, resource_id, details, ip_address, user_agent, status, error_message, session_id, created_at",
            "SELECT COUNT(*)"
        ).replace(" ORDER BY created_at DESC LIMIT ? OFFSET ?", "")
        count_params = params[:-2]  # limit, offset 제외
        
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "logs": logs,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": total_count > offset + len(logs)
        }
        
    except Exception as e:
        logger.error(f"활동 로그 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"활동 로그 조회 실패: {str(e)}")

@app.get("/api/admin/logs/login",
         tags=["ANALYTICS Audit & Logs"], 
         summary="로그인 이력 조회",
         description="""
         ## 로그인 이력 조회
         
         시스템의 로그인 시도 이력을 조회합니다.
         
         ###  필요 권한
         - `system.logs`: 시스템 로그 조회 권한
         
         ### ANALYTICS 조회 옵션
         - **user_id**: 특정 사용자의 로그인 이력만 조회
         - **status**: 성공/실패 상태별 조회
         - **start_date**: 조회 시작 날짜
         - **end_date**: 조회 종료 날짜
         - **limit**: 최대 조회 개수 (기본: 100)
         
         ### LIST 제공 정보
         - 사용자 정보 (ID, 이름, 이메일)
         - 로그인 상태 및 실패 사유
         - IP 주소 및 User-Agent
         - 세션 정보
         - 로그인/로그아웃 시간
         """)
async def get_login_logs(
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user = Depends(require_permission("system.logs"))
):
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        # 기본 쿼리
        query = """
            SELECT id, user_id, username, email, login_type, status, ip_address,
                   user_agent, failure_reason, session_id, login_time, logout_time
            FROM login_history
            WHERE 1=1
        """
        params = []
        
        # 필터 조건 추가
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
            
        if status:
            query += " AND status = ?"
            params.append(status)
            
        if start_date:
            query += " AND login_time >= ?"
            params.append(start_date)
            
        if end_date:
            query += " AND login_time <= ?"
            params.append(end_date)
        
        # 정렬 및 제한
        query += " ORDER BY login_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        logs = []
        
        for row in cursor.fetchall():
            logs.append({
                "id": row[0],
                "user_id": row[1],
                "username": row[2],
                "email": row[3],
                "login_type": row[4],
                "status": row[5],
                "ip_address": row[6],
                "user_agent": row[7],
                "failure_reason": row[8],
                "session_id": row[9],
                "login_time": row[10],
                "logout_time": row[11]
            })
        
        # 총 개수 조회
        count_query = query.replace(
            "SELECT id, user_id, username, email, login_type, status, ip_address, user_agent, failure_reason, session_id, login_time, logout_time",
            "SELECT COUNT(*)"
        ).replace(" ORDER BY login_time DESC LIMIT ? OFFSET ?", "")
        count_params = params[:-2]  # limit, offset 제외
        
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "logs": logs,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": total_count > offset + len(logs)
        }
        
    except Exception as e:
        logger.error(f"로그인 이력 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"로그인 이력 조회 실패: {str(e)}")

@app.get("/api/admin/logs/audit",
         tags=["ANALYTICS Audit & Logs"], 
         summary="감사 로그 조회",
         description="""
         ## 감사 로그 조회
         
         시스템의 중요한 변경 사항에 대한 감사 로그를 조회합니다.
         
         ###  필요 권한
         - `system.logs`: 시스템 로그 조회 권한
         
         ### ANALYTICS 조회 옵션
         - **category**: 카테고리별 조회 (user, role, permission, backup 등)
         - **action**: 액션별 조회 (create, update, delete 등)
         - **user_id**: 특정 사용자의 감사 로그만 조회
         - **target_type**: 대상 유형별 조회
         - **severity**: 심각도별 조회 (info, warning, error, critical)
         - **start_date**: 조회 시작 날짜
         - **end_date**: 조회 종료 날짜
         - **limit**: 최대 조회 개수 (기본: 100)
         
         ### LIST 제공 정보
         - 카테고리 및 액션 정보
         - 사용자 및 대상 정보
         - 변경 전/후 값
         - 심각도 및 상태
         - 상세 내용 및 타임스탬프
         """)
async def get_audit_logs(
    category: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[int] = None,
    target_type: Optional[str] = None,
    severity: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user = Depends(require_permission("system.logs"))
):
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        # 기본 쿼리
        query = """
            SELECT id, category, action, user_id, username, target_type, target_id,
                   old_values, new_values, ip_address, user_agent, severity, status, details, created_at
            FROM audit_logs
            WHERE 1=1
        """
        params = []
        
        # 필터 조건 추가
        if category:
            query += " AND category = ?"
            params.append(category)
            
        if action:
            query += " AND action LIKE ?"
            params.append(f"%{action}%")
            
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
            
        if target_type:
            query += " AND target_type = ?"
            params.append(target_type)
            
        if severity:
            query += " AND severity = ?"
            params.append(severity)
            
        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date)
            
        if end_date:
            query += " AND created_at <= ?"
            params.append(end_date)
        
        # 정렬 및 제한
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        logs = []
        
        for row in cursor.fetchall():
            logs.append({
                "id": row[0],
                "category": row[1],
                "action": row[2],
                "user_id": row[3],
                "username": row[4],
                "target_type": row[5],
                "target_id": row[6],
                "old_values": row[7],
                "new_values": row[8],
                "ip_address": row[9],
                "user_agent": row[10],
                "severity": row[11],
                "status": row[12],
                "details": row[13],
                "created_at": row[14]
            })
        
        # 총 개수 조회
        count_query = query.replace(
            "SELECT id, category, action, user_id, username, target_type, target_id, old_values, new_values, ip_address, user_agent, severity, status, details, created_at",
            "SELECT COUNT(*)"
        ).replace(" ORDER BY created_at DESC LIMIT ? OFFSET ?", "")
        count_params = params[:-2]  # limit, offset 제외
        
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "logs": logs,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": total_count > offset + len(logs)
        }
        
    except Exception as e:
        logger.error(f"감사 로그 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"감사 로그 조회 실패: {str(e)}")

@app.get("/api/admin/logs/stats",
         tags=["ANALYTICS Audit & Logs"], 
         summary="로그 통계 조회",
         description="""
         ## 로그 통계 조회
         
         시스템 로그의 통계 정보를 조회합니다.
         
         ###  필요 권한
         - `system.logs`: 시스템 로그 조회 권한
         
         ### ANALYTICS 통계 정보
         - 일별 활동 통계
         - 사용자별 활동 통계
         - 액션별 통계
         - 로그인 성공/실패 통계
         - 리소스별 접근 통계
         """)
async def get_log_stats(
    days: int = 7,
    current_user = Depends(require_permission("system.logs"))
):
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        # 지정된 일수 이후의 날짜
        from datetime import datetime, timedelta
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # 일별 활동 통계
        cursor.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM activity_logs
            WHERE created_at >= ?
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """, (start_date,))
        
        daily_activity = [
            {"date": row[0], "count": row[1]}
            for row in cursor.fetchall()
        ]
        
        # 액션별 통계
        cursor.execute("""
            SELECT action, COUNT(*) as count
            FROM activity_logs
            WHERE created_at >= ?
            GROUP BY action
            ORDER BY count DESC
            LIMIT 10
        """, (start_date,))
        
        action_stats = [
            {"action": row[0], "count": row[1]}
            for row in cursor.fetchall()
        ]
        
        # 로그인 통계
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM login_history
            WHERE login_time >= ?
            GROUP BY status
        """, (start_date,))
        
        login_stats = [
            {"status": row[0], "count": row[1]}
            for row in cursor.fetchall()
        ]
        
        # 상위 활동 사용자 통계
        cursor.execute("""
            SELECT username, COUNT(*) as count
            FROM activity_logs
            WHERE created_at >= ? AND username IS NOT NULL
            GROUP BY username
            ORDER BY count DESC
            LIMIT 10
        """, (start_date,))
        
        user_stats = [
            {"username": row[0], "count": row[1]}
            for row in cursor.fetchall()
        ]
        
        conn.close()
        
        return {
            "period": f"{days} days",
            "daily_activity": daily_activity,
            "action_stats": action_stats,
            "login_stats": login_stats,
            "user_stats": user_stats
        }
        
    except Exception as e:
        logger.error(f"로그 통계 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"로그 통계 조회 실패: {str(e)}")

# 대시보드 및 리포트 시스템 API 엔드포인트
@app.get("/api/dashboard/overview",
         tags=["ANALYTICS Dashboard & Reports"], 
         summary="대시보드 개요 조회",
         description="""
         ## 대시보드 개요 조회
         
         시스템의 전체적인 현황을 한눈에 볼 수 있는 대시보드 정보를 제공합니다.
         
         ###  필요 권한
         - `system.monitor`: 시스템 모니터링 권한
         
         ### ANALYTICS 제공 정보
         - **시스템 상태**: 데이터베이스 연결, 서버 가동시간, 리소스 사용량
         - **사용자 통계**: 총 사용자 수, 활성 사용자, 역할별 분포
         - **활동 통계**: 오늘/이번 주/이번 달 활동 수
         - **백업 상태**: 최근 백업 정보, 백업 스케줄 상태
         - **알림 현황**: 읽지 않은 알림 수, 최근 알림
         - **보안 현황**: 최근 로그인 실패, 계정 잠금 현황
         """)
async def get_dashboard_overview(current_user = Depends(require_permission("system.monitor"))):
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        from datetime import datetime, timedelta
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        week_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        month_start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        
        # 시스템 상태
        system_status = {
            "database_connected": db_status["connected"],
            "tables_created": db_status["tables_created"],
            "uptime_hours": round((time.time() - monitoring_stats["start_time"]) / 3600, 1),
            "total_requests": monitoring_stats["requests_count"],
            "error_count": monitoring_stats["errors_count"],
            "scheduler_running": scheduler.running if hasattr(scheduler, 'running') else False
        }
        
        # 시스템 리소스
        import psutil
        system_resources = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('./').percent
        }
        
        # 사용자 통계
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
        active_users = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT role, COUNT(*) as count
            FROM users
            GROUP BY role
            ORDER BY count DESC
        """)
        user_roles = [{"role": row[0], "count": row[1]} for row in cursor.fetchall()]
        
        # 활동 통계
        cursor.execute("SELECT COUNT(*) FROM activity_logs WHERE DATE(created_at) = ?", (today,))
        today_activities = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM activity_logs WHERE created_at >= ?", (week_start,))
        week_activities = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM activity_logs WHERE created_at >= ?", (month_start,))
        month_activities = cursor.fetchone()[0]
        
        # 최근 로그인 통계
        cursor.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM login_history 
            WHERE DATE(login_time) = ?
        """, (today,))
        login_data = cursor.fetchone()
        login_stats = {
            "total": login_data[0],
            "success": login_data[1],
            "failed": login_data[2]
        }
        
        # 백업 현황
        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT DATE(created_at) 
                FROM activity_logs 
                WHERE action = 'backup_created' AND created_at >= ?
            )
        """, (month_start,))
        backup_days = cursor.fetchone()[0]
        
        # 최근 백업 정보
        backup_status = {
            "backup_days_this_month": backup_days,
            "scheduler_enabled": BACKUP_SCHEDULE_CONFIG["enabled"],
            "last_backup_time": "N/A",
            "next_backup_time": "N/A"
        }
        
        # 스케줄러가 실행 중이면 다음 백업 시간 조회
        if scheduler.running:
            try:
                jobs = scheduler.get_jobs()
                for job in jobs:
                    if job.id == 'daily_backup' and job.next_run_time:
                        backup_status["next_backup_time"] = job.next_run_time.isoformat()
                        break
            except:
                pass
        
        # 알림 현황
        cursor.execute("SELECT COUNT(*) FROM notifications WHERE is_read = 0")
        unread_notifications = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM notifications 
            WHERE created_at >= ? AND type = 'error'
        """, (today,))
        today_errors = cursor.fetchone()[0]
        
        # 최근 중요한 이벤트
        cursor.execute("""
            SELECT action, username, created_at, details
            FROM activity_logs
            WHERE action IN ('login', 'backup_created', 'user_role_changed', 'permission_granted')
            ORDER BY created_at DESC
            LIMIT 10
        """)
        recent_events = [
            {
                "action": row[0],
                "username": row[1],
                "created_at": row[2],
                "details": row[3]
            }
            for row in cursor.fetchall()
        ]
        
        conn.close()
        
        return {
            "system_status": system_status,
            "system_resources": system_resources,
            "user_statistics": {
                "total_users": total_users,
                "active_users": active_users,
                "user_roles": user_roles
            },
            "activity_statistics": {
                "today": today_activities,
                "week": week_activities,
                "month": month_activities
            },
            "login_statistics": login_stats,
            "backup_status": backup_status,
            "notifications": {
                "unread_count": unread_notifications,
                "today_errors": today_errors
            },
            "recent_events": recent_events,
            "generated_at": now.isoformat()
        }
        
    except Exception as e:
        logger.error(f"대시보드 개요 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"대시보드 개요 조회 실패: {str(e)}")

@app.get("/api/dashboard/system-health",
         tags=["ANALYTICS Dashboard & Reports"], 
         summary="시스템 헬스 체크",
         description="""
         ## 시스템 헬스 체크
         
         시스템의 상세한 건강 상태를 확인합니다.
         
         ###  필요 권한
         - `system.monitor`: 시스템 모니터링 권한
         
         ###  체크 항목
         - **데이터베이스**: 연결 상태, 응답 시간, 테이블 상태
         - **스케줄러**: 백업 스케줄러 상태, 작업 큐 상태
         - **리소스**: CPU, 메모리, 디스크 사용량
         - **서비스**: API 응답 시간, 에러율
         - **보안**: 최근 보안 이벤트, 계정 상태
         """)
async def get_system_health(current_user = Depends(require_permission("system.monitor"))):
    try:
        health_checks = {}
        overall_status = "healthy"
        
        # 데이터베이스 헬스 체크
        db_start = time.time()
        try:
            conn = sqlite3.connect("./data/brandflow.db")
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            cursor.fetchone()
            conn.close()
            db_response_time = round((time.time() - db_start) * 1000, 2)
            
            health_checks["database"] = {
                "status": "healthy",
                "connected": True,
                "response_time_ms": db_response_time,
                "tables_exist": db_status["tables_created"]
            }
        except Exception as e:
            health_checks["database"] = {
                "status": "unhealthy",
                "connected": False,
                "error": str(e)
            }
            overall_status = "unhealthy"
        
        # 스케줄러 헬스 체크
        try:
            scheduler_healthy = scheduler.running if hasattr(scheduler, 'running') else False
            job_count = len(scheduler.get_jobs()) if scheduler_healthy else 0
            
            health_checks["scheduler"] = {
                "status": "healthy" if scheduler_healthy else "warning",
                "running": scheduler_healthy,
                "job_count": job_count,
                "backup_enabled": BACKUP_SCHEDULE_CONFIG["enabled"]
            }
            
            if not scheduler_healthy:
                overall_status = "warning" if overall_status == "healthy" else overall_status
                
        except Exception as e:
            health_checks["scheduler"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            overall_status = "unhealthy"
        
        # 시스템 리소스 헬스 체크
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('./')
            
            resource_status = "healthy"
            if cpu_percent > 80 or memory.percent > 80 or disk.percent > 90:
                resource_status = "warning"
                if overall_status == "healthy":
                    overall_status = "warning"
            
            health_checks["resources"] = {
                "status": resource_status,
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "available_memory_gb": round(memory.available / (1024**3), 2)
            }
        except Exception as e:
            health_checks["resources"] = {
                "status": "unknown",
                "error": str(e)
            }
        
        # API 서비스 헬스 체크
        error_rate = 0
        if monitoring_stats["requests_count"] > 0:
            error_rate = round((monitoring_stats["errors_count"] / monitoring_stats["requests_count"]) * 100, 2)
        
        avg_response_time = 0
        if monitoring_stats["requests_count"] > 0:
            avg_response_time = round(monitoring_stats["total_processing_time"] / monitoring_stats["requests_count"], 3)
        
        api_status = "healthy"
        if error_rate > 5 or avg_response_time > 1000:  # 5% 에러율 또는 1초 이상 응답시간
            api_status = "warning"
            if overall_status == "healthy":
                overall_status = "warning"
        
        health_checks["api_service"] = {
            "status": api_status,
            "uptime_hours": round((time.time() - monitoring_stats["start_time"]) / 3600, 1),
            "total_requests": monitoring_stats["requests_count"],
            "error_rate_percent": error_rate,
            "avg_response_time_ms": avg_response_time
        }
        
        return {
            "overall_status": overall_status,
            "health_checks": health_checks,
            "last_check": datetime.datetime.now().isoformat(),
            "recommendations": get_health_recommendations(health_checks)
        }
        
    except Exception as e:
        logger.error(f"시스템 헬스 체크 오류: {e}")
        raise HTTPException(status_code=500, detail=f"시스템 헬스 체크 실패: {str(e)}")

def get_health_recommendations(health_checks: dict) -> List[str]:
    """헬스 체크 결과에 따른 권장사항 생성"""
    recommendations = []
    
    # 데이터베이스 권장사항
    if health_checks.get("database", {}).get("status") != "healthy":
        recommendations.append("데이터베이스 연결을 확인하고 복구하세요")
    elif health_checks.get("database", {}).get("response_time_ms", 0) > 100:
        recommendations.append("데이터베이스 응답 시간이 느립니다. 인덱스 최적화를 고려하세요")
    
    # 스케줄러 권장사항
    if not health_checks.get("scheduler", {}).get("running", False):
        recommendations.append("백업 스케줄러가 실행되지 않고 있습니다. 스케줄러를 시작하세요")
    
    # 리소스 권장사항
    resources = health_checks.get("resources", {})
    if resources.get("cpu_percent", 0) > 80:
        recommendations.append("CPU 사용률이 높습니다. 시스템 부하를 확인하세요")
    if resources.get("memory_percent", 0) > 80:
        recommendations.append("메모리 사용률이 높습니다. 메모리 정리를 고려하세요")
    if resources.get("disk_percent", 0) > 90:
        recommendations.append("디스크 공간이 부족합니다. 불필요한 파일을 정리하세요")
    
    # API 서비스 권장사항
    api = health_checks.get("api_service", {})
    if api.get("error_rate_percent", 0) > 5:
        recommendations.append("API 에러율이 높습니다. 로그를 확인하세요")
    if api.get("avg_response_time_ms", 0) > 1000:
        recommendations.append("API 응답 시간이 느립니다. 성능 최적화를 고려하세요")
    
    if not recommendations:
        recommendations.append("모든 시스템이 정상적으로 작동 중입니다")
    
    return recommendations

@app.get("/api/dashboard/activity-report",
         tags=["ANALYTICS Dashboard & Reports"], 
         summary="활동 리포트 생성",
         description="""
         ## 활동 리포트 생성
         
         지정된 기간의 상세한 활동 리포트를 생성합니다.
         
         ###  필요 권한
         - `system.monitor`: 시스템 모니터링 권한
         
         ### ANALYTICS 리포트 내용
         - **사용자 활동**: 로그인/로그아웃, 주요 액션 통계
         - **시스템 사용**: API 호출, 기능별 사용 빈도
         - **보안 이벤트**: 로그인 실패, 권한 변경
         - **성능 지표**: 응답 시간, 에러율, 리소스 사용
         - **백업 활동**: 백업 생성, 복원 이력
         """)
async def get_activity_report(
    start_date: str,
    end_date: str,
    report_type: str = "summary",  # summary, detailed, security
    current_user = Depends(require_permission("system.monitor"))
):
    try:
        conn = sqlite3.connect("./data/brandflow.db")
        cursor = conn.cursor()
        
        report_data = {
            "report_type": report_type,
            "period": {"start_date": start_date, "end_date": end_date},
            "generated_by": current_user["username"],
            "generated_at": datetime.datetime.now().isoformat()
        }
        
        # 활동 요약
        cursor.execute("""
            SELECT COUNT(*) as total_activities,
                   COUNT(DISTINCT user_id) as unique_users,
                   COUNT(DISTINCT DATE(created_at)) as active_days
            FROM activity_logs
            WHERE created_at BETWEEN ? AND ?
        """, (start_date, end_date))
        
        summary_data = cursor.fetchone()
        report_data["summary"] = {
            "total_activities": summary_data[0],
            "unique_users": summary_data[1],
            "active_days": summary_data[2]
        }
        
        # 일별 활동 통계
        cursor.execute("""
            SELECT DATE(created_at) as date, 
                   COUNT(*) as activities,
                   COUNT(DISTINCT user_id) as users
            FROM activity_logs
            WHERE created_at BETWEEN ? AND ?
            GROUP BY DATE(created_at)
            ORDER BY date
        """, (start_date, end_date))
        
        report_data["daily_activity"] = [
            {
                "date": row[0],
                "activities": row[1],
                "users": row[2]
            }
            for row in cursor.fetchall()
        ]
        
        # 액션별 통계
        cursor.execute("""
            SELECT action, COUNT(*) as count,
                   COUNT(DISTINCT user_id) as unique_users
            FROM activity_logs
            WHERE created_at BETWEEN ? AND ?
            GROUP BY action
            ORDER BY count DESC
        """, (start_date, end_date))
        
        report_data["action_statistics"] = [
            {
                "action": row[0],
                "count": row[1],
                "unique_users": row[2]
            }
            for row in cursor.fetchall()
        ]
        
        # 사용자별 통계 (상위 10명)
        cursor.execute("""
            SELECT username, COUNT(*) as activities,
                   COUNT(DISTINCT action) as unique_actions,
                   MIN(created_at) as first_activity,
                   MAX(created_at) as last_activity
            FROM activity_logs
            WHERE created_at BETWEEN ? AND ? AND username IS NOT NULL
            GROUP BY username
            ORDER BY activities DESC
            LIMIT 10
        """, (start_date, end_date))
        
        report_data["top_users"] = [
            {
                "username": row[0],
                "activities": row[1],
                "unique_actions": row[2],
                "first_activity": row[3],
                "last_activity": row[4]
            }
            for row in cursor.fetchall()
        ]
        
        # 로그인 통계
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM login_history
            WHERE login_time BETWEEN ? AND ?
            GROUP BY status
        """, (start_date, end_date))
        
        login_stats = {}
        for row in cursor.fetchall():
            login_stats[row[0]] = row[1]
        
        report_data["login_statistics"] = login_stats
        
        # 보안 리포트 (report_type이 security인 경우)
        if report_type in ["security", "detailed"]:
            # 로그인 실패 상세
            cursor.execute("""
                SELECT ip_address, failure_reason, COUNT(*) as attempts,
                       MAX(login_time) as last_attempt
                FROM login_history
                WHERE login_time BETWEEN ? AND ? AND status = 'failed'
                GROUP BY ip_address, failure_reason
                ORDER BY attempts DESC
                LIMIT 20
            """, (start_date, end_date))
            
            report_data["security_events"] = {
                "failed_login_attempts": [
                    {
                        "ip_address": row[0],
                        "reason": row[1],
                        "attempts": row[2],
                        "last_attempt": row[3]
                    }
                    for row in cursor.fetchall()
                ]
            }
            
            # 권한 변경 이력
            cursor.execute("""
                SELECT username, action, target_type, details, created_at
                FROM audit_logs
                WHERE created_at BETWEEN ? AND ?
                AND category IN ('user', 'role', 'permission')
                ORDER BY created_at DESC
                LIMIT 50
            """, (start_date, end_date))
            
            report_data["security_events"]["permission_changes"] = [
                {
                    "username": row[0],
                    "action": row[1],
                    "target_type": row[2],
                    "details": row[3],
                    "created_at": row[4]
                }
                for row in cursor.fetchall()
            ]
        
        conn.close()
        return report_data
        
    except Exception as e:
        logger.error(f"활동 리포트 생성 오류: {e}")
        raise HTTPException(status_code=500, detail=f"활동 리포트 생성 실패: {str(e)}")

if __name__ == "__main__":
    import asyncio
    import uvicorn
    
    # 데이터베이스 초기화 시도
    asyncio.run(init_database())
    
    port = int(os.getenv("PORT", 8000))
    logger.info(f"LAUNCH Starting BrandFlow FastAPI on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)