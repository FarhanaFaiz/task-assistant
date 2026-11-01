from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.main import app


def test_auth_and_task_isolation():
    with TemporaryDirectory() as directory:
        engine = create_engine(
            f"sqlite:///{Path(directory) / 'test.db'}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine)
        TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        def override_get_db():
            db = TestingSession()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        try:
            client = TestClient(app)
            first = client.post(
                "/api/auth/register",
                json={"email": "first@example.com", "password": "password123"},
            )
            second = client.post(
                "/api/auth/register",
                json={"email": "second@example.com", "password": "password123"},
            )
            assert first.status_code == 201
            assert second.status_code == 201

            first_headers = {"Authorization": f"Bearer {first.json()['access_token']}"}
            second_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}
            created = client.post(
                "/api/tasks", headers=first_headers, json={"title": "Private task"}
            )
            assert created.status_code == 201
            task_id = created.json()["id"]
            assert client.get("/api/tasks", headers=second_headers).json() == []
            assert client.get(f"/api/tasks/{task_id}", headers=second_headers).status_code == 404
            assert client.get("/api/tasks", headers=first_headers).json()[0]["title"] == "Private task"
        finally:
            app.dependency_overrides.clear()
            engine.dispose()
