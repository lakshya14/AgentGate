import json
from fastapi import APIRouter, Request, HTTPException, status, Depends, BackgroundTasks
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from config import settings
from agent.graph import build_graph
from dependencies import verify_github_signature
import structlog
router = APIRouter(prefix="/discord", tags=["discord"])

async def resume_agent_in_background(pool, thread_id: str, action: str):
    try:
        graph_app = await build_graph(pool)
        await graph_app.aupdate_state(
            {"configurable": {"thread_id": thread_id}}, 
            {"approval_status": action}, 
            as_node="draft_action"
        )
        await graph_app.ainvoke(None, config={"configurable": {"thread_id": thread_id}})
    except Exception as e:
        structlog.get_logger(__name__).error("discord.background_resume_failed", error=str(e), exc_info=True)

def verify_signature(request_body: bytes, signature: str, timestamp: str) -> bool:
    """
    Verifies the Ed25519 signature from Discord to guarantee payload integrity and authenticity.
    """
    verify_key = VerifyKey(bytes.fromhex(settings.discord_public_key))
    
    message = timestamp.encode() + request_body
    
    try:
        verify_key.verify(message, bytes.fromhex(signature))
        return True
    except BadSignatureError:
        return False

@router.post("/interactions")
async def interactions_webhook(request: Request, background_tasks: BackgroundTasks):
    structlog.contextvars.bind_contextvars(thread_id="test")
    # 1. Get required headers from Discord
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")
    
    if not signature or not timestamp:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature headers")
        
    # 2. Get raw request body
    raw_body = await request.body()
    
    # 3. Verify signature
    if not verify_signature(raw_body, signature, timestamp):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid request signature")
        
    # 4. Parse the JSON body
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")
        
    # Discord requires acknowledging PING (type 1) with PONG (type 1)
    if body.get("type") == 1:
        return {"type": 1}
        
    if body.get("type") == 3:
        custom_id = body.get("data", {}).get("custom_id")
        print(f"Button clicked! Custom ID: {custom_id}")
        
        action, thread_id = custom_id.split('_', 1)
        
        background_tasks.add_task(
            resume_agent_in_background,
            request.app.state.pool,
            thread_id,
            action
        )
        
        # Type 6: DEFERRED_UPDATE_MESSAGE (acknowledge the click immediately)
        return {"type": 6}
    
    return {"status": "ok"}
