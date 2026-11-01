import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL", f"sqlite:///{(BACKEND_DIR / 'task_assistant.db').as_posix()}"
)
if DATABASE_URL == "sqlite:///./task_assistant.db":
    DATABASE_URL = f"sqlite:///{(BACKEND_DIR / 'task_assistant.db').as_posix()}"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-flash-latest")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

if not JWT_SECRET_KEY:
    JWT_SECRET_KEY = "development-only-change-me"
