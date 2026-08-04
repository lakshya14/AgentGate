from fastapi import APIRouter, Depends, Request, Header, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import get_db
from models import GithubEvent
from dependencies import verify_github_signature
from agent.graph import build_graph
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/webhook/github",
    tags=["github"],
    dependencies=[Depends(verify_github_signature)]
)

async def run_agent_in_background(pool, initial_state: dict, thread_id: str):
    try:
        app = await build_graph(pool)
        await app.ainvoke(initial_state, config={"configurable": {"thread_id": thread_id}})
    except Exception as e:
        logger.error("agent.background_run_failed", error=str(e), exc_info=True)

@router.post("")
async def receive_github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(...),
    x_github_delivery: str = Header(...),
    db: Session = Depends(get_db)
):
    structlog.contextvars.bind_contextvars(x_github_delivery=x_github_delivery)
    payload = await request.json()

    try:
        github_event = GithubEvent(
            delivery_id=x_github_delivery, 
            event_type=x_github_event, 
            payload=payload
        )
        db.add(github_event)
        db.commit()
        
        # Trigger the LangGraph background agent for issue events
        if x_github_event == "issues":
            action = payload.get("action")
            if action in ["opened", "reopened"]:
                initial_state = {
                    "event_source": "github",
                    "event_type": "issues",
                    "raw_payload": payload,
                    "suggested_labels": [],
                    "related_issues": [],
                    "actions_taken": []
                }
                background_tasks.add_task(
                    run_agent_in_background,
                    request.app.state.pool,
                    initial_state,
                    x_github_delivery # thread_id
                )
                logger.info("agent.background_task_queued", action=action)

        return {"status": "accepted"}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate delivery_id")
