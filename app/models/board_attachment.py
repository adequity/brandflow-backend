"""
게시판 첨부파일 모델
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from .base import Base


class BoardPostAttachment(Base):
    """게시글 첨부파일 모델"""
    __tablename__ = "board_post_attachments"

    id = Column(Integer, primary_key=True, index=True)

    # 게시글 참조
    post_id = Column(Integer, ForeignKey("board_posts.id", ondelete="CASCADE"), nullable=False, comment="게시글 ID")

    # 파일 정보
    file_url = Column(String(500), nullable=False, comment="파일 URL")
    file_name = Column(String(200), nullable=False, comment="파일 원본 이름")
    file_size = Column(Integer, nullable=False, comment="파일 크기(bytes)")

    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="업로드일시")

    # 관계
    post = relationship("BoardPost", back_populates="attachments")

    def __repr__(self):
        return f"<BoardPostAttachment(id={self.id}, file_name='{self.file_name}')>"
