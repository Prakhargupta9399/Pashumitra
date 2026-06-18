"""
app/models.py
SQLAlchemy ORM models for PashuMitra.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class Farmer(Base):
    __tablename__ = "farmers"

    id         = Column(Integer, primary_key=True, index=True)
    phone      = Column(String(15), unique=True, index=True, nullable=False)
    name       = Column(String(100), nullable=True)
    language   = Column(String(20), default="hindi")
    village    = Column(String(100), nullable=True)
    district   = Column(String(100), nullable=True)
    is_premium = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Farmer phone={self.phone} name={self.name}>"


class QueryLog(Base):
    __tablename__ = "query_logs"

    id         = Column(Integer, primary_key=True, index=True)
    phone      = Column(String(15), index=True, nullable=False)
    query_text = Column(String(500), nullable=True)
    disease    = Column(String(200), nullable=True)
    severity   = Column(String(20), nullable=True)
    language   = Column(String(20), default="hindi")
    helpful    = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
