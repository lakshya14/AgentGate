import structlog
import os
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List
from agent.state import AgentState
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings
from agent.vector_store import search_similar_issues
from agent.notifications import send_approval_message, update_approval_message
from agent.tools import add_labels, post_comment, assign_issue, close_issue
from database import SessionLocal
from models import AuditLog


logger = structlog.get_logger(__name__)

def load_prompt(name: str, version: str = "v1") -> str:
    prompts_dir = Path(__file__).parent / "prompts"
    prompt_file = prompts_dir / f"{name}_{version}.txt"
    return prompt_file.read_text(encoding="utf-8")

# Module-level LLM singleton — constructed once at import time, shared across all node calls.
_llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    temperature=0.2,
    api_key=settings.gemini_api_key
)

# --- Pydantic Models for Structured Output ---

class ClassificationOutput(BaseModel):
    severity: str = Field(description="The severity of the issue (e.g., 'low', 'medium', 'high', 'critical')")
    suggested_labels: List[str] = Field(description="A list of suggested GitHub labels for this issue")

class DraftActionOutput(BaseModel):
    proposed_action: str = Field(description="The proposed action (e.g., 'assign', 'close', 'wait_for_human')")
    action_rationale: str = Field(description="Explanation of why this action was proposed")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")

# --- Nodes ---

async def ingest_node(state: AgentState) -> dict:
    """
    Takes the raw webhook payload and extracts the initial summary and context.
    """
    logger.info("node.ingest", step="start")
    
    payload = state["raw_payload"]
    issue_number = payload["issue"]["number"]
    issue_title = payload["issue"]["title"]
    issue_body = payload["issue"]["body"]
    
    issue_summary = f"Title: {issue_title}\nBody: {issue_body}"
    
    logger.info("node.ingest", step="complete", issue_number=issue_number)
    
    return {
        "issue_summary": issue_summary,
        "issue_number": issue_number
    }

async def classify_node(state: AgentState) -> dict:
    """
    Uses the LLM to classify the severity and suggest labels.
    """
    logger.info("node.classify", step="start")
    
    # Use structured output to ensure we get the exact dictionary keys we need
    structured_llm = _llm.with_structured_output(ClassificationOutput)
    
    prompt_template = load_prompt("classify", version="v1")
    prompt = prompt_template.format(issue_summary=state['issue_summary'])
    
    # Use ainvoke for async execution
    response = await structured_llm.ainvoke(prompt)
    
    logger.info("node.classify", step="complete", severity=response.severity)
    
    return {
        "severity": response.severity,
        "suggested_labels": response.suggested_labels
    }

async def research_node(state: AgentState) -> dict:
    """
    Performs a vector search for similar past issues to add context.
    """
    logger.info("node.research", step="start")
    
    issue_summary = state["issue_summary"]
    related_issues = search_similar_issues(issue_summary)
    
    logger.info("node.research", step="complete", found_issues=len(related_issues))
    
    return {"related_issues": related_issues}

from langchain_core.runnables import RunnableConfig

async def draft_action_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Synthesizes the classification and research to propose an automated action.
    """
    logger.info("node.draft_action", step="start")
    
    structured_llm = _llm.with_structured_output(DraftActionOutput)
    
    prompt_template = load_prompt("draft_action", version="v1")
    prompt = prompt_template.format(
        issue_summary=state['issue_summary'],
        severity=state['severity'],
        suggested_labels=state['suggested_labels'],
        related_issues=state['related_issues']
    )
    
    response = await structured_llm.ainvoke(prompt)
    
    logger.info("node.draft_action", step="complete", action=response.proposed_action)
    
    thread_id = config.get("configurable", {}).get("thread_id", "unknown_thread")
    
    # Send the Discord approval message before moving to the next node
    message_id = await send_approval_message(
        issue_summary=state['issue_summary'],
        severity=state['severity'],
        proposed_action=response.proposed_action,
        thread_id=thread_id
    )
    
    return {
        "proposed_action": response.proposed_action,
        "action_rationale": response.action_rationale,
        "confidence": response.confidence,
        "discord_message_id": message_id
    }

async def execute_action_node(state: AgentState) -> dict:
    """
    Executes the approved action on GitHub.
    This node only runs after a human approves or rejects via Discord.
    Routes to specific GitHub API calls based on `proposed_action` value.
    """
    logger.info("node.execute_action", step="start", action=state.get("proposed_action"))

    message_id = state.get("discord_message_id")
    approval_status = state.get("approval_status")
    issue_number = state["issue_number"]
    issue_summary = state.get("issue_summary", "")
    severity = state.get("severity", "")
    proposed_action = state.get("proposed_action", "")
    action_rationale = state.get("action_rationale", "")
    suggested_labels = state.get("suggested_labels", [])
    suggested_assignee = state.get("suggested_assignee")

    raw_payload = state.get("raw_payload", {})
    repo = raw_payload.get("repository", {}).get("full_name") or settings.github_repo
    token = settings.github_token

    db = SessionLocal()
    try:
        # ─── Rejection Path ───────────────────────────────────────────────────
        if approval_status == "reject":
            logger.info("node.execute_action", step="rejected")

            await update_approval_message(
                message_id=message_id,
                new_status="Action Cancelled",
                executor="human",
                issue_summary=issue_summary,
                severity=severity,
                proposed_action=proposed_action,
                approved=False,
            )
            audit_log = AuditLog(
                action_type="REJECTED",
                executor="human",
                issue_number=issue_number,
            )
            db.add(audit_log)
            db.commit()

            return {"actions_taken": ["Action cancelled by human"]}

        # ─── Approval Path ────────────────────────────────────────────────────
        actions_taken = []

        # Always apply suggested labels if present
        if suggested_labels and repo and token:
            await add_labels(repo=repo, issue_number=issue_number, labels=suggested_labels, token=token)
            actions_taken.append(f"Applied labels: {suggested_labels}")

        # Always post a rationale comment so the GitHub issue has a paper trail
        if repo and token:
            comment = (
                f"**AgentGate Triage**\n\n"
                f"**Proposed Action**: {proposed_action}\n"
                f"**Rationale**: {action_rationale}"
            )
            await post_comment(repo=repo, issue_number=issue_number, body=comment, token=token)
            actions_taken.append("Posted rationale comment on GitHub issue")

        # Route to specific GitHub action based on proposed_action
        if proposed_action == "assign" and suggested_assignee and repo and token:
            await assign_issue(repo=repo, issue_number=issue_number, assignees=[suggested_assignee], token=token)
            actions_taken.append(f"Assigned issue to {suggested_assignee}")

        elif proposed_action == "close" and repo and token:
            await close_issue(repo=repo, issue_number=issue_number, token=token)
            actions_taken.append("Closed GitHub issue")

        elif proposed_action == "wait_for_human":
            actions_taken.append("No automated action taken — flagged for human review")

        else:
            actions_taken.append(f"No specific handler for action '{proposed_action}' — labels and comment applied")

        # Update Discord card to green "Action Executed"
        await update_approval_message(
            message_id=message_id,
            new_status="Action Executed",
            executor="human",
            issue_summary=issue_summary,
            severity=severity,
            proposed_action=proposed_action,
            approved=True,
        )

        audit_log = AuditLog(
            action_type=proposed_action,
            executor="human",
            issue_number=issue_number,
        )
        db.add(audit_log)
        db.commit()

        logger.info("node.execute_action", step="complete", actions=actions_taken)
        return {"actions_taken": actions_taken}

    finally:
        db.close()

