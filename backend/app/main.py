
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.tasks import router as tasks_router
from app.api.goals import router as goals_router
from app.core.config import FRONTEND_URL

app = FastAPI(
    title="Task Assistant API",
    description="AI-powered task management backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(
        {
            FRONTEND_URL,
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
        }
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(tasks_router)
app.include_router(goals_router)
app.include_router(chat_router)


@app.get("/")
def root():
    return {
        "message": "Welcome to Task Assistant API",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "task-assistant-backend",
    }
from app.db.database import initialize_database
from app.db import models

initialize_database()