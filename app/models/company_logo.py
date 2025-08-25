from sqlalchemy import Column, Integer, String, ForeignKey

from .base import Base, TimestampMixin


class CompanyLogo(Base, TimestampMixin):
    __tablename__ = "company_logos"

    id = Column(Integer, primary_key=True, index=True)
    logo_url = Column(String(500), nullable=True)
    company_id = Column(String(100), default="default")
    
    # 외래키
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    def __repr__(self):
        return f"<CompanyLogo(id={self.id}, company_id={self.company_id})>"