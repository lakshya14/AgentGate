from pydantic import BaseModel

# We'll use a generic dict for the payload initially since events vary widely
class GithubWebhookPayload(BaseModel):
    action: str | None = None
    
    model_config = {
        "extra": "allow"
    }
