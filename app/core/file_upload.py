"""
파일 업로드 관리자
다중 파일 업로드, 드래그앤드롭, 파일 유효성 검사 등을 담당
"""

import os
import uuid
import mimetypes
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any, BinaryIO
from fastapi import UploadFile, HTTPException
from PIL import Image
import aiofiles
import aiofiles.os
from datetime import datetime
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class FileUploadError(Exception):
    """파일 업로드 관련 예외"""
    pass

class FileUploadManager:
    """파일 업로드 관리자"""
    
    # 허용된 파일 확장자 및 MIME 타입
    ALLOWED_EXTENSIONS = {
        'images': {
            'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'
        },
        'documents': {
            'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv'
        },
        'archives': {
            'zip', 'rar', '7z', 'tar', 'gz'
        },
        'videos': {
            'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv'
        },
        'audio': {
            'mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a'
        }
    }
    
    # MIME 타입 매핑
    ALLOWED_MIME_TYPES = {
        'image/jpeg', 'image/png', 'image/gif', 'image/webp',
        'image/bmp', 'image/svg+xml',
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'text/plain', 'text/csv',
        'application/zip', 'application/x-rar-compressed',
        'video/mp4', 'video/avi', 'video/quicktime',
        'audio/mpeg', 'audio/wav', 'audio/flac'
    }
    
    def __init__(self, upload_dir: str = "./uploads"):
        self.upload_dir = Path(upload_dir)
        self.max_file_size = getattr(settings, 'MAX_FILE_SIZE', 50 * 1024 * 1024)  # 50MB
        self.max_files_per_upload = 20
        
    async def ensure_upload_dir(self):
        """업로드 디렉토리 확인 및 생성"""
        await aiofiles.os.makedirs(self.upload_dir, exist_ok=True)
        
        # 카테고리별 서브디렉토리 생성
        for category in ['images', 'documents', 'archives', 'videos', 'audio', 'temp']:
            category_dir = self.upload_dir / category
            await aiofiles.os.makedirs(category_dir, exist_ok=True)
    
    def get_file_category(self, filename: str) -> str:
        """파일 확장자로 카테고리 결정"""
        ext = Path(filename).suffix.lower().lstrip('.')
        
        for category, extensions in self.ALLOWED_EXTENSIONS.items():
            if ext in extensions:
                return category
        
        return 'documents'  # 기본값
    
    def validate_file(self, file: UploadFile) -> Dict[str, Any]:
        """파일 유효성 검사"""
        if not file.filename:
            raise FileUploadError("파일명이 없습니다.")
        
        # 파일 크기 검사
        if hasattr(file.file, 'seek') and hasattr(file.file, 'tell'):
            file.file.seek(0, 2)  # 파일 끝으로 이동
            size = file.file.tell()
            file.file.seek(0)  # 파일 시작으로 복귀
            
            if size > self.max_file_size:
                raise FileUploadError(f"파일 크기가 너무 큽니다. 최대 {self.max_file_size // (1024*1024)}MB")
        
        # 확장자 검사
        ext = Path(file.filename).suffix.lower().lstrip('.')
        all_extensions = set()
        for exts in self.ALLOWED_EXTENSIONS.values():
            all_extensions.update(exts)
        
        if ext not in all_extensions:
            raise FileUploadError(f"허용되지 않는 파일 형식입니다: .{ext}")
        
        # MIME 타입 검사
        if file.content_type and file.content_type not in self.ALLOWED_MIME_TYPES:
            logger.warning(f"MIME type not in allowed list: {file.content_type} for file {file.filename}")
        
        return {
            'filename': file.filename,
            'content_type': file.content_type,
            'size': getattr(file, 'size', 0),
            'category': self.get_file_category(file.filename),
            'extension': ext
        }
    
    def generate_unique_filename(self, original_filename: str) -> str:
        """고유한 파일명 생성"""
        ext = Path(original_filename).suffix.lower()
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        
        # 안전한 파일명 생성 (특수문자 제거)
        safe_name = "".join(c for c in Path(original_filename).stem if c.isalnum() or c in ('-', '_'))
        safe_name = safe_name[:50]  # 길이 제한
        
        return f"{safe_name}_{timestamp}_{unique_id}{ext}"
    
    async def save_file(self, file: UploadFile, custom_filename: Optional[str] = None) -> Dict[str, Any]:
        """단일 파일 저장"""
        await self.ensure_upload_dir()
        
        # 파일 유효성 검사
        file_info = self.validate_file(file)
        
        # 파일명 생성
        filename = custom_filename or self.generate_unique_filename(file.filename)
        category = file_info['category']
        
        # 저장 경로 결정
        file_path = self.upload_dir / category / filename
        
        try:
            # 파일 저장
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
            
            # 파일 해시 계산 (중복 검사용)
            file_hash = hashlib.md5(content).hexdigest()
            
            # 이미지인 경우 썸네일 생성
            thumbnail_path = None
            if category == 'images' and file_info['extension'] in {'jpg', 'jpeg', 'png', 'webp'}:
                thumbnail_path = await self.create_thumbnail(file_path)
            
            return {
                'filename': filename,
                'original_filename': file.filename,
                'file_path': str(file_path),
                'relative_path': f"{category}/{filename}",
                'category': category,
                'size': len(content),
                'content_type': file.content_type,
                'hash': file_hash,
                'thumbnail_path': thumbnail_path,
                'uploaded_at': datetime.utcnow()
            }
            
        except Exception as e:
            # 오류 시 파일 삭제
            try:
                await aiofiles.os.remove(file_path)
            except:
                pass
            raise FileUploadError(f"파일 저장 실패: {str(e)}")
    
    async def save_multiple_files(self, files: List[UploadFile]) -> List[Dict[str, Any]]:
        """다중 파일 저장"""
        if len(files) > self.max_files_per_upload:
            raise FileUploadError(f"한 번에 최대 {self.max_files_per_upload}개 파일만 업로드 가능합니다.")
        
        results = []
        failed_files = []
        
        for file in files:
            try:
                result = await self.save_file(file)
                results.append(result)
            except FileUploadError as e:
                failed_files.append({
                    'filename': file.filename,
                    'error': str(e)
                })
                logger.error(f"Failed to save file {file.filename}: {e}")
        
        return {
            'success': results,
            'failed': failed_files,
            'total_uploaded': len(results),
            'total_failed': len(failed_files)
        }
    
    async def create_thumbnail(self, image_path: Path, size: tuple = (200, 200)) -> Optional[str]:
        """이미지 썸네일 생성"""
        try:
            thumbnail_dir = self.upload_dir / 'images' / 'thumbnails'
            await aiofiles.os.makedirs(thumbnail_dir, exist_ok=True)
            
            # 썸네일 파일명
            thumbnail_filename = f"thumb_{image_path.stem}.jpg"
            thumbnail_path = thumbnail_dir / thumbnail_filename
            
            # PIL로 썸네일 생성 (동기 작업)
            with Image.open(image_path) as img:
                img.thumbnail(size, Image.Resampling.LANCZOS)
                # RGBA -> RGB 변환 (JPEG 저장을 위해)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                img.save(thumbnail_path, 'JPEG', quality=85)
            
            return f"images/thumbnails/{thumbnail_filename}"
            
        except Exception as e:
            logger.error(f"Failed to create thumbnail for {image_path}: {e}")
            return None
    
    async def delete_file(self, file_path: str) -> bool:
        """파일 삭제"""
        try:
            full_path = self.upload_dir / file_path
            await aiofiles.os.remove(full_path)
            
            # 썸네일이 있다면 함께 삭제
            if file_path.startswith('images/'):
                filename = Path(file_path).name
                thumbnail_path = self.upload_dir / 'images' / 'thumbnails' / f"thumb_{Path(filename).stem}.jpg"
                try:
                    await aiofiles.os.remove(thumbnail_path)
                except:
                    pass
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """파일 정보 조회"""
        full_path = self.upload_dir / file_path
        
        if not full_path.exists():
            raise FileUploadError("파일을 찾을 수 없습니다.")
        
        stat = full_path.stat()
        mime_type, _ = mimetypes.guess_type(str(full_path))
        
        return {
            'filename': full_path.name,
            'file_path': str(full_path),
            'relative_path': file_path,
            'size': stat.st_size,
            'content_type': mime_type,
            'modified_at': datetime.fromtimestamp(stat.st_mtime),
            'category': self.get_file_category(full_path.name)
        }
    
    async def cleanup_old_files(self, days: int = 30):
        """오래된 임시 파일 정리"""
        temp_dir = self.upload_dir / 'temp'
        if not temp_dir.exists():
            return
        
        cutoff_time = datetime.utcnow().timestamp() - (days * 24 * 60 * 60)
        deleted_count = 0
        
        for file_path in temp_dir.rglob('*'):
            if file_path.is_file():
                try:
                    stat = file_path.stat()
                    if stat.st_mtime < cutoff_time:
                        await aiofiles.os.remove(file_path)
                        deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete old file {file_path}: {e}")
        
        logger.info(f"Cleaned up {deleted_count} old files from temp directory")
        return deleted_count

# 전역 파일 업로드 관리자 인스턴스
file_manager = FileUploadManager(upload_dir=settings.UPLOAD_DIR)