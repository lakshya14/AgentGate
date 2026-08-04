import sys
import asyncio
from agent.graph import build_graph

from psycopg_pool import AsyncConnectionPool
from config import settings

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def main():
    print("Initializing Connection Pool for test...")
    pool = AsyncConnectionPool(conninfo=settings.database_url, open=False, kwargs={"autocommit": True})
    await pool.open()
    
    print("Building graph...")
    app = await build_graph(pool) # We now inject the pool!
    
    # We must define a config with a thread_id so the checkpointer knows which conversation this is
    config = {"configurable": {"thread_id": "test_process_restart_1"}} # elaborate on the role of config here
    
    # ??? Your logic here:
    # 1. Fetch the current state using app.get_state(config)
    # 2. Check if the state has any values (e.g., if state.values is empty).
    # 3. If it IS empty: 
    #    - Create a small initial_state dictionary with a mock 'raw_payload' (like in smoke_test.py)
    #    - Run `await app.ainvoke(initial_state, config)`
    #    - Print "Graph executed and state saved."
    # 4. If it is NOT empty:
    #    - Print "State successfully restored from Postgres!"
    #    - Print out the `state.values` to prove it works.
    current_state = await app.aget_state(config)
    mock_payload = {
        "action": "opened",
        "issue": {
            "number": 42,
            "title": "Application crashes on startup",
            "body": "When I start the app with Docker, it immediately exits with exit code 1. Here are the logs..."
        }
    }
    if not current_state.values:
        initial_state = {'raw_payload': mock_payload}
        await app.ainvoke(initial_state, config)
        print("Graph executed and state saved.")
    else:
        print("State successfully restored from Postgres!")
        print(current_state.values)
    print("\n--- DONE ---")
    
    print("Closing connection pool...")
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
