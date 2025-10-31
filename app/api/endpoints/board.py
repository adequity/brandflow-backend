"""
게시판 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import joinedload
from typing import List, Optional
from datetime import datetime
import os
import shutil
from pathlib import Path

from app.db.database import get_async_db
from app.models import User, BoardPost, PostType, UserRole, BoardPostAttachment
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
    - 같은 회사(company)의 게시글만 조회
    """
    # company가 없는 사용자는 빈 결과 반환
    if not current_user.company:
        return {
            "success": True,
            "posts": [],
            "total": 0,
            "skip": skip,
            "limit": limit
        }

    query = select(BoardPost).options(
        joinedload(BoardPost.author),  # author를 eager loading
        joinedload(BoardPost.attachments)  # attachments를 eager loading
    ).where(
        and_(
            BoardPost.is_deleted == False,
            BoardPost.company == current_user.company  # 회사별 필터링
        )
    )

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
    posts = result.scalars().unique().all()  # unique() 추가 (joinedload 사용 시 필요)

    # 총 개수 조회
    count_query = select(func.count(BoardPost.id)).where(
        and_(
            BoardPost.is_deleted == False,
            BoardPost.company == current_user.company  # 회사별 필터링
        )
    )
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
                "attachments": [
                    {
                        "id": att.id,
                        "fileUrl": att.file_url,
                        "fileName": att.file_name,
                        "fileSize": att.file_size,
                        "createdAt": att.created_at.isoformat()
                    }
                    for att in post.attachments
                ],
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
    - 같은 회사의 게시글만 조회
    """
    # company가 없는 사용자는 접근 불가
    if not current_user.company:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    query = select(BoardPost).options(
        joinedload(BoardPost.author),  # author를 eager loading
        joinedload(BoardPost.attachments)  # attachments를 eager loading
    ).where(
        and_(
            BoardPost.id == post_id,
            BoardPost.is_deleted == False,
            BoardPost.company == current_user.company  # 회사별 필터링
        )
    )
    result = await db.execute(query)
    post = result.scalars().unique().one_or_none()

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
            "attachments": [
                {
                    "id": att.id,
                    "fileUrl": att.file_url,
                    "fileName": att.file_name,
                    "fileSize": att.file_size,
                    "createdAt": att.created_at.isoformat()
                }
                for att in post.attachments
            ],
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
    files: List[UploadFile] = File([]),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    게시글 생성
    - agency_admin만 가능
    - 다중 파일 업로드 지원
    """
    check_agency_admin(current_user)

    # company가 없는 사용자는 게시글 생성 불가
    if not current_user.company:
        raise HTTPException(status_code=400, detail="회사 정보가 없어 게시글을 작성할 수 없습니다.")

    # 게시글 생성 (첨부파일 없이 먼저 생성)
    new_post = BoardPost(
        title=title,
        content=content,
        post_type=PostType(post_type),
        is_notice=is_notice,
        is_popup=is_popup,
        popup_start_date=parse_datetime(popup_start_date),
        popup_end_date=parse_datetime(popup_end_date),
        author_id=current_user.id,
        company=current_user.company
    )

    db.add(new_post)
    await db.commit()
    await db.refresh(new_post)

    # 다중 파일 업로드 처리
    if files and len(files) > 0:
        for file in files:
            if file.filename:
                # 파일 저장
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
                safe_filename = f"{timestamp}_{file.filename}"
                file_path = UPLOAD_DIR / safe_filename

                with file_path.open("wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                # BoardPostAttachment 생성
                attachment = BoardPostAttachment(
                    post_id=new_post.id,
                    file_url=f"/uploads/board/{safe_filename}",
                    file_name=file.filename,
                    file_size=file_path.stat().st_size
                )
                db.add(attachment)

        await db.commit()

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
    files: List[UploadFile] = File([]),
    remove_attachment_ids: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    게시글 수정
    - agency_admin만 가능
    - 같은 회사의 게시글만 수정 가능
    - 다중 파일 업로드 지원
    """
    check_agency_admin(current_user)

    # company가 없는 사용자는 접근 불가
    if not current_user.company:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    query = select(BoardPost).options(
        joinedload(BoardPost.attachments)
    ).where(
        and_(
            BoardPost.id == post_id,
            BoardPost.is_deleted == False,
            BoardPost.company == current_user.company  # 회사별 필터링
        )
    )
    result = await db.execute(query)
    post = result.scalars().unique().one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    # 삭제할 첨부파일 처리
    if remove_attachment_ids:
        ids_to_remove = [int(id.strip()) for id in remove_attachment_ids.split(",") if id.strip()]
        for attachment in post.attachments:
            if attachment.id in ids_to_remove:
                # 파일 삭제
                file_path = Path(f".{attachment.file_url}")
                if file_path.exists():
                    file_path.unlink()
                # DB에서 삭제
                await db.delete(attachment)

    # 새 파일 업로드
    if files and len(files) > 0:
        for file in files:
            if file.filename:
                # 파일 저장
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
                safe_filename = f"{timestamp}_{file.filename}"
                file_path = UPLOAD_DIR / safe_filename

                with file_path.open("wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                # BoardPostAttachment 생성
                attachment = BoardPostAttachment(
                    post_id=post.id,
                    file_url=f"/uploads/board/{safe_filename}",
                    file_name=file.filename,
                    file_size=file_path.stat().st_size
                )
                db.add(attachment)

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
    - 같은 회사의 게시글만 삭제 가능
    """
    check_agency_admin(current_user)

    # company가 없는 사용자는 접근 불가
    if not current_user.company:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    query = select(BoardPost).where(
        and_(
            BoardPost.id == post_id,
            BoardPost.is_deleted == False,
            BoardPost.company == current_user.company  # 회사별 필터링
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
    - 같은 회사의 게시글만 조회
    """
    # company가 없는 사용자는 빈 결과 반환
    if not current_user.company:
        return {
            "success": True,
            "posts": []
        }

    now = datetime.utcnow()

    query = select(BoardPost).options(
        joinedload(BoardPost.author)  # author를 eager loading
    ).where(
        and_(
            BoardPost.is_deleted == False,
            BoardPost.is_popup == True,
            BoardPost.company == current_user.company,  # 회사별 필터링
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
    posts = result.scalars().unique().all()  # unique() 추가

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
