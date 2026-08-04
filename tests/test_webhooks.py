import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db
from dependencies import verify_github_signature
import models

# Setup isolated SQLite in-memory database for testing
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

async def override_verify_github_signature():
    return True

# Register FastAPI dependency overrides
app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[verify_github_signature] = override_verify_github_signature

def test_github_webhook_ingestion():
    """
    Smoke test to ensure the /webhook/github endpoint can ingest an event,
    validate it (bypassed by override), and persist to the isolated test database.
    """
    mock_payload = {
        "issue": {
            "number": 123,
            "title": "Fix login bug",
            "body": "Users are getting a 500 when logging in."
        },
        "repository": {
            "full_name": "AgentGate/test-repo"
        }
    }
    
    mock_headers = {
        "X-GitHub-Event": "issues",
        "X-GitHub-Delivery": "test-delivery-id-123",
    }

    with TestClient(app) as client:
        response = client.post(
            "/webhook/github", 
            json=mock_payload, 
            headers=mock_headers
        )
        assert response.status_code == 200
        assert response.json() == {"status": "accepted"}


