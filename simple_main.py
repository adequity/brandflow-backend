# BrandFlow FastAPI v2.0.0 - 점진적 기능 복원
from fastapi import FastAPI, HTTPException, Depends, Request, UploadFile, File
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
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
from typing import Optional, Dict, Any, List

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
    """새 알림 생성"""
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
        return notification_id
    except Exception as e:
        logger.error(f"알림 생성 오류: {e}")
        return None

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 BrandFlow FastAPI v2.0.0 시작 중...")
    await init_database()
    logger.info("✅ BrandFlow 서버 준비 완료!")
    
    yield
    
    # Shutdown  
    logger.info("🛑 BrandFlow 서버 종료 중...")

app = FastAPI(
    title="BrandFlow API v2.0.0",
    description="BrandFlow 캠페인 관리 시스템 - Railway 배포",
    version="2.0.0",
    lifespan=lifespan
)

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

@app.get("/")
async def root():
    return {
        "message": "BrandFlow FastAPI v2.0.0 - Railway Test", 
        "status": "running",
        "port": os.getenv("PORT", "unknown"),
        "database": db_status["connected"]
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "database": "connected" if db_status["connected"] else "disconnected"
    }

@app.get("/db/status")
async def database_status():
    """데이터베이스 연결 상태 확인"""
    return {
        "connected": db_status["connected"],
        "error": db_status["error"],
        "tables_created": db_status["tables_created"],
        "database_url": "sqlite:///./data/brandflow.db" if db_status["connected"] else "not_configured"
    }

# 인증 API 엔드포인트들
@app.post("/api/auth/login-json", response_model=Token)
async def login(login_request: LoginRequest):
    """사용자 로그인"""
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

@app.post("/api/campaigns")
async def create_new_campaign(campaign_data: CampaignCreate, token: str = Depends(security)):
    """새 캠페인 생성"""
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
@app.post("/api/purchase-orders")
async def create_purchase_order_request(po_data: PurchaseOrderCreate, token: str = Depends(security)):
    """발주요청 생성"""
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
        logger.info("🔄 데이터베이스 연결 시도 중...")
        
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            logger.info("✅ 기본 테스트 사용자 생성: test@brandflow.com / test123")
        
        conn.close()
        
        db_status["connected"] = True
        db_status["tables_created"] = True
        db_status["error"] = None
        logger.info("✅ 데이터베이스 연결 및 테이블 생성 완료")
        
    except Exception as e:
        db_status["connected"] = False
        db_status["tables_created"] = False
        db_status["error"] = str(e)
        logger.warning(f"⚠️ 데이터베이스 초기화 실패: {e}")
        logger.info("🚀 데이터베이스 없이 API 모드로 계속 진행")

if __name__ == "__main__":
    import asyncio
    import uvicorn
    
    # 데이터베이스 초기화 시도
    asyncio.run(init_database())
    
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🚀 Starting BrandFlow FastAPI on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)