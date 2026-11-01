from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent.service import build_tools
from app.db.database import Base, get_db
from app.db.models import User
from app.main import app


@pytest.fixture
def client_and_session():
    with TemporaryDirectory() as directory:
        engine = create_engine(
            f"sqlite:///{Path(directory) / 'metadata.db'}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        def override_get_db():
            db = session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        try:
            yield TestClient(app), session_factory
        finally:
            app.dependency_overrides.clear()
            engine.dispose()


def auth_headers(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "metadata@example.com", "password": "password123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_task_metadata_filters_and_sorting(client_and_session):
    client, _ = client_and_session
    headers = auth_headers(client)
    first = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "Urgent CV",
            "priority": "urgent",
            "category": "Career",
            "estimated_minutes": 120,
            "due_date": "2030-01-02T10:00:00Z",
        },
    )
    second = client.post(
        "/api/tasks",
        headers=headers,
        json={"title": "Low reading", "priority": "low", "category": "Study"},
    )
    assert first.status_code == 201
    assert first.json()["estimated_minutes"] == 120
    assert first.json()["category"] == "Career"
    assert client.get("/api/tasks?priority=urgent", headers=headers).json()[0]["title"] == "Urgent CV"
    assert client.get("/api/tasks?category=Study", headers=headers).json()[0]["title"] == "Low reading"
    assert client.get("/api/tasks?completed=false&sort=priority", headers=headers).status_code == 200

    updated = client.patch(
        f"/api/tasks/{first.json()['id']}",
        headers=headers,
        json={"priority": "high", "estimated_minutes": 90},
    )
    assert updated.status_code == 200
    assert updated.json()["priority"] == "high"
    assert updated.json()["estimated_minutes"] == 90


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "Bad priority", "priority": "critical"},
        {"title": "Bad duration", "estimated_minutes": 0},
    ],
)
def test_invalid_task_metadata_is_rejected(client_and_session, payload):
    client, _ = client_and_session
    assert client.post("/api/tasks", headers=auth_headers(client), json=payload).status_code == 422


def test_ai_tools_create_metadata_for_authenticated_user(client_and_session):
    client, session_factory = client_and_session
    headers = auth_headers(client)
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    db = session_factory()
    try:
        user = db.get(User, user_id)
        tools = build_tools(db, user)
        created = tools[1](
            "Tool task",
            priority="urgent",
            due_date="2030-02-03T09:00:00Z",
            category="Work",
            estimated_minutes=45,
        )
        assert created["priority"] == "urgent"
        assert created["category"] == "Work"
        assert created["estimated_minutes"] == 45
    finally:
        db.close()
