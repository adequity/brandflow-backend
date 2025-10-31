"""
게시판 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import List, Optional
from datetime import datetime
import os
import shutil
from pathlib import Path

from app.db.database import get_async_db
from app.models import User, BoardPost, PostType, UserRole
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/api/board", tags=["board"])


# 파일 업로드 디렉토리
UPLOAD_DIR = Path("./uploads/board")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def check_agency_admin(current_user: User):
    """agency_admin 권한 체크"""
    if current_user.role != UserRole.AGENCY_ADMIN:
        raise HTTPException(status_code=403, detail="게시글 작성 권한이 없습니다. agency_admin만 가능합니다.")
    return True


def parse_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """
    ISO 8601 형식 날짜 문자열을 datetime으로 안전하게 파싱
    - 2025-10-24T00:00:00.000Z
    - 2025-10-24T00:00:00Z
    - 2025-10-24
    """
    if not date_str:
        return None

    try:
        # ISO format with milliseconds and Z
        if 'T' in date_str:
            # Remove 'Z' suffix if present
            clean_str = date_str.rstrip('Z')
            # Try parsing with milliseconds
            try:
                return datetime.fromisoformat(clean_str)
            except:
                # Try without milliseconds
                return datetime.strptime(clean_str.split('.')[0], "%Y-%m-%dT%H:%M:%S")
        else:
            # Simple date format (2025-10-24)
            return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"날짜 형식이 잘못되었습니다: {date_str}")


@router.get("/posts")
async def get_board_posts(
    post_type: Optional[str] = None,
    is_notice: Optional[bool] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    게시글 목록 조회
    - 모든 사용자가 조회 가능
    - 삭제되지 않은 게시글만 반환
    """
    query = select(BoardPost).where(BoardPost.is_deleted == False)

    # 필터링
    if post_type:
        query = query.where(BoardPost.post_type == post_type)
    if is_notice is not None:
        query = query.where(BoardPost.is_notice == is_notice)

    # 정렬: 공지사항 우선, 최신순
    query = query.order_by(
        BoardPost.is_notice.desc(),
        BoardPost.created_at.desc()
    )

    # 페이지네이션
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    posts = result.scalars().all()

    # 총 개수 조회
    count_query = select(func.count(BoardPost.id)).where(BoardPost.is_deleted == False)
    if post_type:
        count_query = count_query.where(BoardPost.post_type == post_type)
    if is_notice is not None:
        count_query = count_query.where(BoardPost.is_notice == is_notice)

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return {
        "success": True,
        "posts": [
            {
                "id": post.id,
                "title": post.title,
                "content": post.content,
                "postType": post.post_type,
                "isNotice": post.is_notice,
                "isPopup": post.is_popup,
                "popupStartDate": post.popup_start_date.isoformat() if post.popup_start_date else None,
                "popupEndDate": post.popup_end_date.isoformat() if post.popup_end_date else None,
                "attachmentUrl": post.attachment_url,
                "attachmentName": post.attachment_name,
                "attachmentSize": post.attachment_size,
                "viewCount": post.view_count,
                "authorId": post.author_id,
                "authorName": post.author.name if post.author else None,
                "createdAt": post.created_at.isoformat(),
                "updatedAt": post.updated_at.isoformat()
            }
            for post in posts
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/posts/{post_id}")
async def get_board_post(
    post_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    게시글 상세 조회
    - 조회수 증가
    """
    query = select(BoardPost).where(
        and_(
            BoardPost.id == post_id,
            BoardPost.is_deleted == False
        )
    )
    result = await db.execute(query)
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    # 조회수 증가
    post.view_count += 1
    await db.commit()

    return {
        "success": True,
        "post": {
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "postType": post.post_type,
            "isNotice": post.is_notice,
            "isPopup": post.is_popup,
            "popupStartDate": post.popup_start_date.isoformat() if post.popup_start_date else None,
            "popupEndDate": post.popup_end_date.isoformat() if post.popup_end_date else None,
            "attachmentUrl": post.attachment_url,
            "attachmentName": post.attachment_name,
            "attachmentSize": post.attachment_size,
            "viewCount": post.view_count,
            "authorId": post.author_id,
            "authorName": post.author.name if post.author else None,
            "createdAt": post.created_at.isoformat(),
            "updatedAt": post.updated_at.isoformat()
        }
    }


@router.post("/posts")
async def create_board_post(
    title: str = Form(...),
    content: str = Form(...),
    post_type: str = Form("general"),
    is_notice: bool = Form(False),
    is_popup: bool = Form(False),
    popup_start_date: Optional[str] = Form(None),
    popup_end_date: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    게시글 생성
    - agency_admin만 가능
    - 파일 업로드 지원
    """
    check_agency_admin(current_user)

    # 파일 업로드 처리
    attachment_url = None
    attachment_name = None
    attachment_size = None

    if file and file.filename:
        # 파일 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = os.path.splitext(file.filename)[1]
        safe_filename = f"{timestamp}_{file.filename}"
        file_path = UPLOAD_DIR / safe_filename

        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        attachment_url = f"/uploads/board/{safe_filename}"
        attachment_name = file.filename
        attachment_size = file_path.stat().st_size

    # 게시글 생성
    new_post = BoardPost(
        title=title,
        content=content,
        post_type=PostType(post_type),
        is_notice=is_notice,
        is_popup=is_popup,
        popup_start_date=parse_datetime(popup_start_date),
        popup_end_date=parse_datetime(popup_end_date),
        attachment_url=attachment_url,
        attachment_name=attachment_name,
        attachment_size=attachment_size,
        author_id=current_user.id
    )

    db.add(new_post)
    await db.commit()
    await db.refresh(new_post)

    return {
        "success": True,
        "message": "게시글이 등록되었습니다.",
        "post": {
            "id": new_post.id,
            "title": new_post.title,
            "postType": new_post.post_type,
            "isNotice": new_post.is_notice,
            "isPopup": new_post.is_popup
        }
    }


@router.put("/posts/{post_id}")
async def update_board_post(
    post_id: int,
    title: str = Form(...),
    content: str = Form(...),
    post_type: str = Form("general"),
    is_notice: bool = Form(False),
    is_popup: bool = Form(False),
    popup_start_date: Optional[str] = Form(None),
    popup_end_date: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    remove_attachment: bool = Form(False),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    게시글 수정
    - agency_admin만 가능
    """
    check_agency_admin(current_user)

    query = select(BoardPost).where(
        and_(
            BoardPost.id == post_id,
            BoardPost.is_deleted == False
        )
    )
    result = await db.execute(query)
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    # 기존 첨부파일 처리
    if remove_attachment and post.attachment_url:
        # 파일 삭제
        old_file_path = Path(f".{post.attachment_url}")
        if old_file_path.exists():
            old_file_path.unlink()
        post.attachment_url = None
        post.attachment_name = None
        post.attachment_size = None

    # 새 파일 업로드
    if file and file.filename:
        # 기존 파일 삭제
        if post.attachment_url:
            old_file_path = Path(f".{post.attachment_url}")
            if old_file_path.exists():
                old_file_path.unlink()

        # 새 파일 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"
        file_path = UPLOAD_DIR / safe_filename

        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        post.attachment_url = f"/uploads/board/{safe_filename}"
        post.attachment_name = file.filename
        post.attachment_size = file_path.stat().st_size

    # 게시글 정보 업데이트
    post.title = title
    post.content = content
    post.post_type = PostType(post_type)
    post.is_notice = is_notice
    post.is_popup = is_popup
    post.popup_start_date = parse_datetime(popup_start_date)
    post.popup_end_date = parse_datetime(popup_end_date)
    post.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(post)

    return {
        "success": True,
        "message": "게시글이 수정되었습니다.",
        "post": {
            "id": post.id,
            "title": post.title
        }
    }


@router.delete("/posts/{post_id}")
async def delete_board_post(
    post_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    게시글 삭제 (soft delete)
    - agency_admin만 가능
    """
    check_agency_admin(current_user)

    query = select(BoardPost).where(
        and_(
            BoardPost.id == post_id,
            BoardPost.is_deleted == False
        )
    )
    result = await db.execute(query)
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    # Soft delete
    post.is_deleted = True
    post.deleted_at = datetime.utcnow()

    await db.commit()

    return {
        "success": True,
        "message": "게시글이 삭제되었습니다."
    }


@router.get("/popup-posts")
async def get_popup_posts(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    대시보드 팝업 게시글 조회
    - 현재 시간 기준으로 활성화된 팝업만 반환
    """
    now = datetime.utcnow()

    query = select(BoardPost).where(
        and_(
            BoardPost.is_deleted == False,
            BoardPost.is_popup == True,
            or_(
                BoardPost.popup_start_date == None,
                BoardPost.popup_start_date <= now
            ),
            or_(
                BoardPost.popup_end_date == None,
                BoardPost.popup_end_date >= now
            )
        )
    ).order_by(BoardPost.created_at.desc())

    result = await db.execute(query)
    posts = result.scalars().all()

    return {
        "success": True,
        "posts": [
            {
                "id": post.id,
                "title": post.title,
                "content": post.content,
                "createdAt": post.created_at.isoformat()
            }
            for post in posts
        ]
    }
