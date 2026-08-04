import operator
from typing import Annotated, TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    # --- Ingestion Data ---
    event_source: str                           # Where the event came from (e.g., "github")
    event_type: str                             # The specific event trigger (e.g., "issues")
    raw_payload: Dict[str, Any]                 # The complete JSON payload from the webhook for reference
    
    issue_number: Optional[int]                 # Extracted GitHub issue number
    issue_summary: Optional[str]                # Condensed title + body of the issue
    
    # --- Classification Data ---
    severity: Optional[str]                     # LLM-assigned severity (e.g., "low", "critical")
    # Annotated with operator.add means this list will append, not overwrite
    suggested_labels: Annotated[List[str], operator.add] # Labels the agent thinks should be applied
    suggested_assignee: Optional[str]           # Who the agent thinks should fix it
    
    # --- Research Data ---
    related_issues: Annotated[List[Dict[str, Any]], operator.add] # Past issues found via vector similarity search
    confidence: Optional[float]                 # 0.0 to 1.0 score of how sure the agent is about its proposed action
    
    # --- Proposed Action (Pre-Approval) ---
    proposed_action: Optional[str]              # The specific action to take (e.g., "assign", "close", "wait_for_human")
    action_rationale: Optional[str]             # The LLM's reasoning for proposing this action
    
    # --- Human-in-the-Loop (HITL) State ---
    approval_thread_id: Optional[str]           # Link back to the parent thread or issue
    discord_message_id: str                     # The Discord Message ID used to dynamically update the UI (remove buttons)
    approval_status: Optional[str]              # "approved" or "rejected" from the human in Discord
    rejection_reason: Optional[str]             # Optional text input if the human explains why they rejected it
    
    # --- Execution & Post-Processing ---
    actions_taken: Annotated[List[str], operator.add] # Append-only log of mutations the agent actually performed on GitHub
    error: Optional[str]                        # Any terminal error caught during graph execution
