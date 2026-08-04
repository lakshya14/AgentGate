import httpx
from config import settings

async def send_approval_message(issue_summary: str, severity: str, proposed_action: str, thread_id: str):
    """
    Sends a rich embed message to Discord with Approve and Reject buttons.
    """
    payload = {
        "embeds": [{
            "title": "AI Agent Triage",
            "description": issue_summary,
            "color": 16711680, # Red
            "fields": [
                {"name": "Severity", "value": severity, "inline": True},
                {"name": "Proposed Action", "value": proposed_action, "inline": False}
            ]
        }],
        "components": [{
            "type": 1,  
            "components": [
                {
                    "type": 2, 
                    "custom_id": f"approve_{thread_id}",
                    "label": "Approve",
                    "style": 3 # Green
                },
                {
                    "type": 2, 
                    "custom_id": f"reject_{thread_id}",
                    "label": "Reject",
                    "style": 4 # Red
                }
            ]
        }]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url=f"https://discord.com/api/v10/channels/{settings.discord_channel_id}/messages",
            headers={
                "Authorization": f"Bot {settings.discord_bot_token}",
            },
            json=payload # httpx uses `json=` instead of `payload=`
        )
        response.raise_for_status() # Ensure we catch HTTP errors
        return response.json()["id"]

async def update_approval_message(
    message_id: str,
    new_status: str,
    executor: str,
    issue_summary: str = "",
    severity: str = "",
    proposed_action: str = "",
    approved: bool = False,
):
    """
    Updates the existing Discord message to show the final execution status
    and removes the interactive buttons.
    Preserves original issue context (summary, severity, proposed action) in the embed.
    Uses green for Approved, red for Rejected.
    Docs: https://discord.com/developers/docs/resources/message#edit-message
    """
    color = 3066993 if approved else 15158332  # Green: #2ecc71, Red: #e74c3c

    fields = []
    if severity:
        fields.append({"name": "Severity", "value": severity, "inline": True})
    if proposed_action:
        fields.append({"name": "Proposed Action", "value": proposed_action, "inline": False})
    fields.append({"name": "Status", "value": f"{new_status} by {executor}", "inline": False})

    payload = {
        "embeds": [{
            "title": "AI Agent Triage",
            "description": issue_summary or new_status,
            "color": color,
            "fields": fields,
        }],
        "components": []  # Removes Approve / Reject buttons
    }

    async with httpx.AsyncClient() as client:
        response = await client.patch(
            url=f"https://discord.com/api/v10/channels/{settings.discord_channel_id}/messages/{message_id}",
            headers={
                "Authorization": f"Bot {settings.discord_bot_token}",
            },
            json=payload
        )
        response.raise_for_status()
        return response.json()["id"]
