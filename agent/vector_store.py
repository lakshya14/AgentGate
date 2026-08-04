from sqlalchemy import select
from sqlalchemy.orm import Session, Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from config import settings
from database import Base, engine  # Single source of truth for Base and engine

import structlog
logger = structlog.get_logger(__name__)

# IssueModel is now registered under the shared Base from database.py.
# This means Alembic's --autogenerate will detect and migrate this table correctly.
class IssueModel(Base):
    __tablename__ = "embedded_issues"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issue_number: Mapped[int] = mapped_column(unique=True)
    issue_text: Mapped[str] = mapped_column()
    # Here is the magic: We define a column that holds a 768-dimensional vector!
    embedding: Mapped[Vector] = mapped_column(Vector(768))


def embed_text(text_content: str) -> list[float]:
    """
    Uses langchain-google-genai to generate a 768-dimensional embedding.
    """
    embeddings = GoogleGenerativeAIEmbeddings(
        model="text-embedding-004",
        output_dimensionality=768,
        google_api_key=settings.gemini_api_key,
    )
    vector = embeddings.embed_query(text_content)
    return vector

def store_issue_embedding(issue_number: int, text_content: str):
    """
    Generates embedding for the text and stores it in the database.
    """
    try:
        embedding = embed_text(text_content)
        with Session(engine) as session:
            issue = IssueModel(issue_number=issue_number, issue_text=text_content, embedding=embedding)
            session.add(issue)
            session.commit()
    except Exception as e:
        logger.warning("Failed to store embedding. DB might be offline.", error=str(e))
        
    
def search_similar_issues(query_text: str, limit: int = 3) -> list[dict]:
    """
    Embeds the query text and performs a cosine similarity search on the database.
    Returns the top 'limit' closest issues.
    """
    try:
        query_embedding = embed_text(query_text)
        with Session(engine) as session:
            results = session.scalars(select(IssueModel).order_by(IssueModel.embedding.cosine_distance(query_embedding)).limit(limit))
            return [{"issue_number": row.issue_number, "text": row.issue_text} for row in results]
    except Exception as e:
        logger.warning("DB offline. Returning mock similar issues.", error=str(e))
        return [{"issue_number": 999, "text": "Mock past issue: App crashed on iOS 13."}]