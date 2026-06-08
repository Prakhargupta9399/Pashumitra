"""
app/database.py
SQLAlchemy setup — uses DATABASE_URL from environment.
Defaults to SQLite for local/phase1 testing.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pashumitra.db")

# SQLite needs connect_args; other DBs don't
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for FastAPI / manual usage."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
