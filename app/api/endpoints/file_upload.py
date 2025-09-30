"""
파일 업로드 엔드포인트
다중 파일 업로드, 드래그앤드롭, 파일 관리 API
"""

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Form, Query
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Optional
import os
from pathlib import Path

from app.core.file_upload import file_manager, FileUploadError
from app.api.deps import get_current_active_user
from app.models.user import User
from app.core.websocket import manager

router = APIRouter()

@router.post("/single")
async def upload_single_file(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user)
):
    """
    단일 파일 업로드
    
    - **file**: 업로드할 파일
    - **description**: 파일 설명 (선택사항)
    """
    try:
        result = await file_manager.save_file(file)
        
        # 성공 알림 전송
        await manager.send_to_user(current_user.id, {
            "type": "file_upload_success",
            "title": "파일 업로드 완료",
            "message": f"'{result['original_filename']}'이 성공적으로 업로드되었습니다.",
            "data": result
        })
        
        return {
            "success": True,
            "message": "파일이 성공적으로 업로드되었습니다.",
            "data": result
        }
        
    except FileUploadError as e:
        # 실패 알림 전송
        await manager.send_to_user(current_user.id, {
            "type": "file_upload_error",
            "title": "파일 업로드 실패",
            "message": str(e),
            "severity": "error"
        })
        
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/multiple")
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    description: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user)
):
    """
    다중 파일 업로드 (드래그앤드롭 지원)
    
    - **files**: 업로드할 파일들
    - **description**: 파일 설명 (선택사항)
    """
    try:
        result = await file_manager.save_multiple_files(files)
        
        # 업로드 결과 알림 전송
        await manager.send_to_user(current_user.id, {
            "type": "multiple_upload_complete",
            "title": "다중 파일 업로드 완료",
            "message": f"{result['total_uploaded']}개 파일 업로드 완료, {result['total_failed']}개 실패",
            "data": result
        })
        
        return {
            "success": True,
            "message": f"총 {len(files)}개 파일 중 {result['total_uploaded']}개가 업로드되었습니다.",
            "data": result
        }
        
    except FileUploadError as e:
        await manager.send_to_user(current_user.id, {
            "type": "multiple_upload_error",
            "title": "다중 파일 업로드 실패",
            "message": str(e),
            "severity": "error"
        })
        
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/info")
async def get_upload_info():
    """
    파일 업로드 정보 조회
    - 허용된 파일 형식
    - 최대 파일 크기
    - 기타 제한사항
    """
    return {
        "allowed_extensions": file_manager.ALLOWED_EXTENSIONS,
        "max_file_size": file_manager.max_file_size,
        "max_file_size_mb": file_manager.max_file_size // (1024 * 1024),
        "max_files_per_upload": file_manager.max_files_per_upload,
        "allowed_mime_types": sorted(list(file_manager.ALLOWED_MIME_TYPES))
    }

@router.get("/list")
async def list_files(
    category: Optional[str] = Query(None, description="파일 카테고리 필터"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_user)
):
    """
    업로드된 파일 목록 조회
    
    - **category**: 파일 카테고리 (images, documents, archives, videos, audio)
    - **limit**: 조회할 파일 수 제한
    """
    try:
        upload_dir = file_manager.upload_dir
        files = []
        
        if category:
            # 특정 카테고리만 조회
            category_dir = upload_dir / category
            if category_dir.exists():
                for file_path in category_dir.glob('*'):
                    if file_path.is_file() and not file_path.name.startswith('.'):
                        try:
                            info = file_manager.get_file_info(f"{category}/{file_path.name}")
                            files.append(info)
                        except:
                            continue
        else:
            # 모든 카테고리 조회
            for cat in file_manager.ALLOWED_EXTENSIONS.keys():
                category_dir = upload_dir / cat
                if category_dir.exists():
                    for file_path in category_dir.glob('*'):
                        if file_path.is_file() and not file_path.name.startswith('.'):
                            try:
                                info = file_manager.get_file_info(f"{cat}/{file_path.name}")
                                files.append(info)
                            except:
                                continue
        
        # 수정시간 기준 내림차순 정렬
        files.sort(key=lambda x: x['modified_at'], reverse=True)
        
        return {
            "files": files[:limit],
            "total": len(files),
            "category": category
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 목록 조회 실패: {str(e)}")

@router.get("/download/{category}/{filename}")
async def download_file(
    category: str,
    filename: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    파일 다운로드

    - **category**: 파일 카테고리
    - **filename**: 파일명
    """
    try:
        from urllib.parse import unquote

        # URL 디코딩 처리 (한글 파일명 지원)
        decoded_filename = unquote(filename)
        file_path = f"{category}/{decoded_filename}"
        full_path = file_manager.upload_dir / file_path

        if not full_path.exists():
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

        return FileResponse(
            path=str(full_path),
            filename=decoded_filename,
            media_type='application/octet-stream'
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 다운로드 실패: {str(e)}")

@router.get("/view/{category}/{filename}")
async def view_file(
    category: str,
    filename: str
):
    """
    파일 뷰어 (이미지, PDF 등)

    - **category**: 파일 카테고리
    - **filename**: 파일명
    """
    try:
        from urllib.parse import unquote
        import mimetypes

        # URL 디코딩 처리 (한글 파일명 지원)
        decoded_filename = unquote(filename)
        print(f"🔍 Original filename: {filename}")
        print(f"🔍 Decoded filename: {decoded_filename}")

        file_path = f"{category}/{decoded_filename}"
        full_path = file_manager.upload_dir / file_path

        print(f"🔍 Full path: {full_path}")
        print(f"🔍 File exists: {full_path.exists()}")

        if not full_path.exists():
            print(f"❌ 파일이 존재하지 않음: {file_path}")
            raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {file_path}")

        # MIME 타입 직접 추정 (file_manager 의존성 제거)
        content_type, _ = mimetypes.guess_type(str(full_path))
        if not content_type:
            # 확장자 기반으로 기본 MIME 타입 설정
            ext = decoded_filename.lower().split('.')[-1]
            if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                content_type = f'image/{ext}' if ext != 'jpg' else 'image/jpeg'
            else:
                content_type = 'application/octet-stream'

        print(f"🔍 Content-Type: {content_type}")

        return FileResponse(
            path=str(full_path),
            filename=decoded_filename,
            media_type=content_type
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 파일 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"파일 조회 실패: {str(e)}")

@router.get("/thumbnail/{filename}")
async def get_thumbnail(
    filename: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    이미지 썸네일 조회
    
    - **filename**: 원본 파일명 (확장자 제외)
    """
    try:
        thumbnail_filename = f"thumb_{Path(filename).stem}.jpg"
        thumbnail_path = file_manager.upload_dir / 'images' / 'thumbnails' / thumbnail_filename
        
        if not thumbnail_path.exists():
            raise HTTPException(status_code=404, detail="썸네일을 찾을 수 없습니다.")
        
        return FileResponse(
            path=str(thumbnail_path),
            filename=thumbnail_filename,
            media_type='image/jpeg'
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"썸네일 조회 실패: {str(e)}")

@router.delete("/{category}/{filename}")
async def delete_file(
    category: str,
    filename: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    파일 삭제
    
    - **category**: 파일 카테고리
    - **filename**: 파일명
    """
    try:
        # 관리자 권한 확인
        if current_user.role not in ["admin", "슈퍼 어드민", "대행사 어드민"]:
            raise HTTPException(status_code=403, detail="파일 삭제 권한이 없습니다.")
        
        file_path = f"{category}/{filename}"
        success = await file_manager.delete_file(file_path)
        
        if success:
            # 삭제 성공 알림
            await manager.send_to_user(current_user.id, {
                "type": "file_delete_success",
                "title": "파일 삭제 완료",
                "message": f"'{filename}' 파일이 삭제되었습니다."
            })
            
            return {"success": True, "message": "파일이 성공적으로 삭제되었습니다."}
        else:
            raise HTTPException(status_code=500, detail="파일 삭제에 실패했습니다.")
            
    except Exception as e:
        await manager.send_to_user(current_user.id, {
            "type": "file_delete_error",
            "title": "파일 삭제 실패",
            "message": str(e),
            "severity": "error"
        })
        
        raise HTTPException(status_code=500, detail=f"파일 삭제 실패: {str(e)}")

@router.post("/cleanup")
async def cleanup_old_files(
    days: int = Query(30, ge=1, le=365, description="삭제할 파일의 경과 일수"),
    current_user: User = Depends(get_current_active_user)
):
    """
    오래된 임시 파일 정리 (관리자 전용)
    
    - **days**: 경과 일수 (기본값: 30일)
    """
    # 관리자 권한 확인
    if current_user.role not in ["admin", "슈퍼 어드민"]:
        raise HTTPException(status_code=403, detail="파일 정리 권한이 없습니다.")
    
    try:
        deleted_count = await file_manager.cleanup_old_files(days)
        
        await manager.send_to_role("admin", {
            "type": "file_cleanup_complete",
            "title": "파일 정리 완료",
            "message": f"{deleted_count}개의 오래된 파일이 삭제되었습니다."
        })
        
        return {
            "success": True,
            "message": f"{deleted_count}개의 오래된 파일이 정리되었습니다.",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 정리 실패: {str(e)}")

@router.get("/stats")
async def get_upload_stats(
    current_user: User = Depends(get_current_active_user)
):
    """
    파일 업로드 통계 (관리자 전용)
    """
    if current_user.role not in ["admin", "슈퍼 어드민", "대행사 어드민"]:
        raise HTTPException(status_code=403, detail="통계 조회 권한이 없습니다.")
    
    try:
        upload_dir = file_manager.upload_dir
        stats = {
            "total_files": 0,
            "total_size": 0,
            "by_category": {}
        }
        
        for category in file_manager.ALLOWED_EXTENSIONS.keys():
            category_dir = upload_dir / category
            if category_dir.exists():
                files = list(category_dir.glob('*'))
                file_count = len([f for f in files if f.is_file()])
                total_size = sum(f.stat().st_size for f in files if f.is_file())
                
                stats["by_category"][category] = {
                    "file_count": file_count,
                    "total_size": total_size,
                    "total_size_mb": round(total_size / (1024 * 1024), 2)
                }
                
                stats["total_files"] += file_count
                stats["total_size"] += total_size
        
        stats["total_size_mb"] = round(stats["total_size"] / (1024 * 1024), 2)
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")