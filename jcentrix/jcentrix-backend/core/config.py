from pydantic_settings import BaseSettings
from typing import List, Optional
from dotenv import load_dotenv
import os

# Force load the .env file and override any existing environment variables to prevent stale shell caches.
load_dotenv(override=True)

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Jcentrix AI Job Portal"
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/jcentrix"
    SYNC_DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/jcentrix"
    
    # ChromaDB Configuration
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    
    # Security
    SECRET_KEY: str = "supersecretkey_please_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # AI
    # OpenAI is NOT used. Groq (below) handles all AI features.
    # OPENAI_API_KEY removed — use GROQ_API_KEY instead.
    GROQ_API_KEY: str = "your-groq-api-key-here"
    
    # Storage
    STORAGE_PATH: str = "./storage"

    # Super Admin Bootstrap
    SUPERADMIN_EMAIL: Optional[str] = None
    SUPERADMIN_PASSWORD: Optional[str] = None
    SUPERADMIN_FULL_NAME: str = "Super Admin"

    class Config:
        env_file = ".env"
        extra = "ignore" # Ignore extra fields in .env to prevent validation errors

    def get_cors_origins(self) -> List[str]:
        """Converts the comma-separated string from .env into a Python list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

settings = Settings()
