from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    """Single shared declarative base for all ORM models in the project."""
    pass

def get_db():
    """
    FastAPI dependency to inject a database session into endpoints.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
