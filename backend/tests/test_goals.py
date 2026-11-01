from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.main import app


def test_goals_milestones_and_isolation():
    with TemporaryDirectory() as directory:
        engine = create_engine(
            f"sqlite:///{Path(directory) / 'goals.db'}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine)
        sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        def override_get_db():
            db = sessions()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        try:
            client = TestClient(app)
            first = client.post("/api/auth/register", json={"email": "goal1@example.com", "password": "password123"})
            second = client.post("/api/auth/register", json={"email": "goal2@example.com", "password": "password123"})
            first_headers = {"Authorization": "Bearer " + first.json()["access_token"]}
            second_headers = {"Authorization": "Bearer " + second.json()["access_token"]}

            created = client.post(
                "/api/goals",
                headers=first_headers,
                json={"title": "Become full-stack", "description": "Build and ship projects", "progress": 10},
            )
            assert created.status_code == 201
            goal = created.json()
            assert goal["task_ids"] == []

            milestone = client.post(
                f"/api/goals/{goal['id']}/milestones",
                headers=first_headers,
                json={"title": "Learn backend fundamentals"},
            )
            assert milestone.status_code == 201
            assert client.patch(
                f"/api/goals/{goal['id']}/milestones/{milestone.json()['id']}",
                headers=first_headers,
                json={"status": "completed"},
            ).json()["status"] == "completed"

            task = client.post(
                "/api/tasks",
                headers=first_headers,
                json={"title": "Build API", "milestone_id": milestone.json()["id"]},
            )
            assert task.status_code == 201
            assert client.get(f"/api/goals/{goal['id']}", headers=first_headers).json()["task_ids"] == [task.json()["id"]]
            milestone_view = client.get(f"/api/goals/{goal['id']}", headers=first_headers).json()["milestones"][0]
            assert milestone_view["task_count"] == 1
            assert client.get("/api/goals", headers=second_headers).json() == []
            assert client.get(f"/api/goals/{goal['id']}", headers=second_headers).status_code == 404
            assert client.post(
                f"/api/goals/{goal['id']}/milestones",
                headers=second_headers,
                json={"title": "Should fail"},
            ).status_code == 404
        finally:
            app.dependency_overrides.clear()
            engine.dispose()


def test_task_milestone_linking_and_removal():
    with TemporaryDirectory() as directory:
        engine = create_engine(
            f"sqlite:///{Path(directory) / 'links.db'}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine)
        sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        def override_get_db():
            db = sessions()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        try:
            client = TestClient(app)
            first = client.post("/api/auth/register", json={"email": "link1@example.com", "password": "password123"})
            second = client.post("/api/auth/register", json={"email": "link2@example.com", "password": "password123"})
            first_headers = {"Authorization": "Bearer " + first.json()["access_token"]}
            second_headers = {"Authorization": "Bearer " + second.json()["access_token"]}
            goal = client.post("/api/goals", headers=first_headers, json={"title": "Goal"}).json()
            milestone = client.post(
                f"/api/goals/{goal['id']}/milestones",
                headers=first_headers,
                json={"title": "Milestone"},
            ).json()

            linked = client.post(
                "/api/tasks",
                headers=first_headers,
                json={"title": "Linked", "milestone_id": milestone["id"]},
            )
            assert linked.status_code == 201
            assert linked.json()["goal_id"] == goal["id"]
            assert linked.json()["milestone_id"] == milestone["id"]

            moved = client.patch(
                f"/api/tasks/{linked.json()['id']}",
                headers=first_headers,
                json={"milestone_id": None},
            )
            assert moved.status_code == 200
            assert moved.json()["milestone_id"] is None

            assert client.post(
                "/api/tasks",
                headers=second_headers,
                json={"title": "Forbidden", "milestone_id": milestone["id"]},
            ).status_code == 404
            assert client.post(
                "/api/tasks",
                headers=first_headers,
                json={"title": "Invalid", "milestone_id": 999999},
            ).status_code == 404
        finally:
            app.dependency_overrides.clear()
            engine.dispose()
