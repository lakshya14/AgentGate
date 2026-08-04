from sqlalchemy import Column, Integer, String, JSON, DateTime
from sqlalchemy.sql import func
from database import Base

class GithubEvent(Base):
    """
    Stores raw webhook payloads immediately upon ingestion.
    Serves as our immutable source of truth for replayability.
    """
    __tablename__ = "github_events"

    id = Column(Integer, primary_key=True, index=True)
    delivery_id = Column(String, unique=True, index=True, nullable=False) # X-GitHub-Delivery header (used for Idempotency)
    event_type = Column(String, nullable=False)                           # X-GitHub-Event header (e.g., 'issues', 'pull_request')
    payload = Column(JSON, nullable=False)                                # Full raw JSON for later debugging/replay
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AuditLog(Base):
    """
    Postgres model to record executed actions for auditing.
    Serves as the clean 'business ledger' of actions actually taken.
    """
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    action_type = Column(String, nullable=False)                          # e.g., 'assign', 'close', or 'REJECTED'
    issue_number = Column(Integer, nullable=False)                        # The GitHub issue this relates to
    executor = Column(String, nullable=False)                             # Who pulled the trigger (e.g., 'human', 'agent')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
