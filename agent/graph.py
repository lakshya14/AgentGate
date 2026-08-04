import sys
import asyncio
from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes import ingest_node, classify_node, research_node, draft_action_node, execute_action_node
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from config import settings

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def build_graph(pool: AsyncConnectionPool):
    # 1. Initialize the StateGraph with our TypedDict
    workflow = StateGraph(AgentState)
    
    # 2. Add nodes (the players in the game)
    workflow.add_node("ingest", ingest_node)
    workflow.add_node("classify", classify_node)
    workflow.add_node("research", research_node)
    workflow.add_node("draft_action", draft_action_node)
    workflow.add_node("execute_action", execute_action_node)
    
    # 3. Define the edges (the flow)
    # Start -> ingest -> classify -> research -> draft_action -> execute_action -> End
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "classify")
    workflow.add_edge("classify", "research")
    workflow.add_edge("research", "draft_action")
    workflow.add_edge("draft_action", "execute_action")
    workflow.add_edge("execute_action", END)
    
    # 4. Use the injected AsyncConnectionPool
    checkpointer = AsyncPostgresSaver(pool)
    
    # 5. Define retry policies for network-dependent nodes
    from langgraph.pregel import RetryPolicy
    default_retry = RetryPolicy(max_attempts=3, backoff_factor=2)
    
    app = workflow.compile(
        checkpointer=checkpointer, 
        interrupt_before=["execute_action"],
        node_retry_policies={
            "classify": default_retry,
            "research": default_retry,
            "draft_action": default_retry,
            "execute_action": default_retry
        }
    )
    return app

