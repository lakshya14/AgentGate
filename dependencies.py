from fastapi import Header, HTTPException, Request
import hmac
import hashlib
from config import settings

async def verify_github_signature(
    request: Request,
    x_hub_signature_256: str = Header(None)
):
    """
    Dependency to verify the GitHub webhook signature using HMAC-SHA256.
    """
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature-256 header")

    # Read the raw request body
    body = await request.body()
    secret = settings.github_webhook_secret.encode()

    expected_hmac = hmac.new(key=secret, msg=body, digestmod=hashlib.sha256).hexdigest()
    expected_signature = f"sha256={expected_hmac}"
    
    if not hmac.compare_digest(expected_signature, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
async def verify_discord_signature(request_body: bytes, signature: str, timestamp: str) -> bool:
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
