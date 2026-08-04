from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    github_webhook_secret: str
    database_url: str
    gemini_api_key: str
    discord_public_key: str
    discord_bot_token: str
    discord_channel_id: str
    github_token: str = ""       # GitHub PAT or App Installation Token for REST API calls
    github_repo: str = ""         # Target repository in "owner/repo" format
    
    # LangSmith Tracing
    langsmith_tracing: str = ""
    langsmith_endpoint: str = ""
    langsmith_api_key: str = ""
    langsmith_project: str = ""
    
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
