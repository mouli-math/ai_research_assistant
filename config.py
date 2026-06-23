import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = "gpt-4o"
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "http://localhost:8001")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    MAX_RETRIES: int = 3
    TIMEOUT: int = 60
    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
    GCP_REGION: str = os.getenv("GCP_REGION", "asia-south1")


config = Config()
