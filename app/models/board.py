"""
게시판 모델
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from .base import Base


class PostType(str, enum.Enum):
    """게시글 타입"""
    NOTICE = "notice"  # 공지사항
    GENERAL = "general"  # 일반 게시글
    MANUAL = "manual"  # 메뉴얼
    RESOURCE = "resource"  # 자료실


class BoardPost(Base):
    """게시판 게시글 모델"""
    __tablename__ = "board_posts"

    id = Column(Integer, primary_key=True, index=True)

    # 게시글 정보
    title = Column(String(200), nullable=False, comment="제목")
    content = Column(Text, nullable=False, comment="내용")
    post_type = Column(SQLEnum(PostType), default=PostType.GENERAL, nullable=False, comment="게시글 타입")

    # 공지사항 관련
    is_notice = Column(Boolean, default=False, nullable=False, comment="공지사항 여부")
    is_popup = Column(Boolean, default=False, nullable=False, comment="대시보드 팝업 여부")
    popup_start_date = Column(DateTime, nullable=True, comment="팝업 시작일")
    popup_end_date = Column(DateTime, nullable=True, comment="팝업 종료일")

    # 파일 첨부
    attachment_url = Column(String(500), nullable=True, comment="첨부파일 URL")
    attachment_name = Column(String(200), nullable=True, comment="첨부파일 원본 이름")
    attachment_size = Column(Integer, nullable=True, comment="첨부파일 크기(bytes)")

    # 통계
    view_count = Column(Integer, default=0, nullable=False, comment="조회수")

    # 작성자 정보
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="작성자 ID")
    author = relationship("User", foreign_keys=[author_id], backref="board_posts")

    # 회사 정보 (다중 회사 분리를 위함)
    company = Column(String(200), nullable=True, comment="소속 회사 (작성자의 company와 동일)")

    # 첨부파일 관계 (다중 파일 지원)
    attachments = relationship("BoardPostAttachment", back_populates="post", cascade="all, delete-orphan")

    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="생성일시")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="수정일시")

    # 삭제 관리
    is_deleted = Column(Boolean, default=False, nullable=False, comment="삭제 여부")
    deleted_at = Column(DateTime, nullable=True, comment="삭제일시")

    def __repr__(self):
        return f"<BoardPost(id={self.id}, title='{self.title}', type='{self.post_type}')>"
