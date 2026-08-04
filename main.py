from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from routers import github, discord
from database import SessionLocal
from models import GithubEvent, AuditLog

from contextlib import asynccontextmanager
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from config import settings
import structlog

# Configure structlog globally
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars, # This is the magic that merges our ContextVars into every log line!
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    conninfo = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
    pool = AsyncConnectionPool(conninfo=conninfo, open=False, kwargs={"autocommit": True}) #initilaze the connection pool
    await pool.open() # opens the connection pool
    checkpointer = AsyncPostgresSaver(pool) # setup the checkpointer
    await checkpointer.setup()
    app.state.pool = pool
    try:    
        yield
    finally:
        await pool.close()

app = FastAPI(
    title="AgentGate", 
    description="Event-driven autonomous GitHub triage agent",
    lifespan=lifespan
)

app.include_router(github.router)
app.include_router(discord.router)

@app.get("/health")
async def health_check():
    pool = app.state.pool
    try:
        async with pool.connection() as conn:
            await conn.execute("SELECT 1")
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status
    }

@app.get("/metrics")
def get_metrics():
    db = SessionLocal()
    try:
        events_count = db.query(GithubEvent).count()
        audit_count = db.query(AuditLog).count()
        return {
            "github_events_processed": events_count,
            "actions_executed": audit_count
        }
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
