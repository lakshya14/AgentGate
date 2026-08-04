import asyncio
from psycopg_pool import AsyncConnectionPool
from agent.graph import build_graph
from config import settings

async def main():
    print("Building graph...")
    # Initialize the DB pool just for this script run
    conninfo = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
    async with AsyncConnectionPool(conninfo=conninfo, kwargs={"autocommit": True}) as pool:
        app = await build_graph(pool)
        
        # Mock GitHub issue payload
        mock_payload = {
            "action": "opened",
            "issue": {
                "number": 42,
                "title": "Application crashes on startup",
                "body": "When I start the app with Docker, it immediately exits with exit code 1. Here are the logs..."
            }
        }
        
        # Initial state
        initial_state = {
            "event_source": "github",
            "event_type": "issues",
            "raw_payload": mock_payload,
            "suggested_labels": [],
            "related_issues": [],
            "actions_taken": []
        }
        
        print("Running graph...\n")
        # Invoke the graph
        final_state = await app.ainvoke(initial_state, config={"configurable": {"thread_id": "smoke_test_1"}})
        
        print("\n--- FINAL STATE ---")
        print(f"Severity: {final_state.get('severity')}")
        print(f"Labels: {final_state.get('suggested_labels')}")
        print(f"Proposed Action: {final_state.get('proposed_action')}")
        print(f"Confidence: {final_state.get('confidence')}")

if __name__ == "__main__":
    asyncio.run(main())
