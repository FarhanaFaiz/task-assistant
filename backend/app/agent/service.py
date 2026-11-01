import logging
import asyncio
import json
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import GEMINI_FALLBACK_MODEL, GEMINI_MODEL, GOOGLE_API_KEY
from app.db.models import Goal, Milestone, Task, User
from app.schemas.goals import BreakdownProposal

logger = logging.getLogger(__name__)
VALID_PRIORITIES = {"low", "medium", "high", "urgent"}


def extract_final_text(events: Iterable[Any]) -> str | None:
    """Return the latest model text, ignoring intermediate tool-call events."""
    fallback_result: str | None = None
    for event in reversed(list(events)):
        if getattr(event, "error_code", None) or getattr(event, "error_message", None):
            logger.error(
                "ADK event reported an error: code=%s message=%s",
                event.error_code,
                event.error_message,
            )
            continue
        content = getattr(event, "content", None)
        for part in reversed(getattr(content, "parts", []) if content else []):
            text = getattr(part, "text", None)
            if isinstance(text, str) and text.strip():
                return text.strip()
            function_call = getattr(part, "function_call", None)
            if function_call and getattr(function_call, "name", None) == "finish_task":
                result = getattr(function_call, "args", {}).get("result")
                if isinstance(result, str) and result.strip():
                    fallback_result = result.strip()
    return fallback_result


def build_tools(db: Session, user: User):
    def task_data(task: Task) -> dict:
        return {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "completed": task.completed,
            "priority": task.priority,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "category": task.category,
            "estimated_minutes": task.estimated_minutes,
            "goal_id": task.goal_id,
            "milestone_id": task.milestone_id,
        }

    def validate_metadata(
        priority: str = "medium",
        due_date: str | None = None,
        estimated_minutes: int | None = None,
    ) -> tuple[str, datetime | None, int | None]:
        if priority not in VALID_PRIORITIES:
            raise ValueError("priority must be low, medium, high, or urgent")
        if estimated_minutes is not None and estimated_minutes <= 0:
            raise ValueError("estimated_minutes must be positive")
        parsed_due_date = None
        if due_date:
            try:
                parsed_due_date = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError("due_date must be an ISO datetime") from error
        return priority, parsed_due_date, estimated_minutes

    def list_tasks(include_completed: bool = True) -> list[dict]:
        """List tasks belonging to the authenticated user."""
        query = select(Task).where(Task.owner_id == user.id)
        if not include_completed:
            query = query.where(Task.completed.is_(False))
        return [
            task_data(task)
            for task in db.scalars(query.order_by(Task.created_at.desc()))
        ]

    def add_task(
        title: str,
        description: str = "",
        priority: str = "medium",
        due_date: str | None = None,
        category: str | None = None,
        estimated_minutes: int | None = None,
        goal_id: int | None = None,
        milestone_id: int | None = None,
        remove_milestone: bool = False,
    ) -> dict:
        """Add a task for the authenticated user with optional planning metadata."""
        priority, due_date, estimated_minutes = validate_metadata(
            priority, due_date, estimated_minutes
        )
        if milestone_id is not None:
            milestone = db.scalar(
                select(Milestone).join(Goal).where(
                    Milestone.id == milestone_id, Goal.owner_id == user.id
                )
            )
            if milestone is None:
                return {"error": "Milestone not found"}
            if goal_id is not None and goal_id != milestone.goal_id:
                return {"error": "Milestone does not belong to goal"}
            goal_id = milestone.goal_id
        elif goal_id is not None and db.scalar(
            select(Goal).where(Goal.id == goal_id, Goal.owner_id == user.id)
        ) is None:
            return {"error": "Goal not found"}
        task = Task(
            title=title,
            description=description or None,
            priority=priority,
            due_date=due_date,
            category=category,
            estimated_minutes=estimated_minutes,
            goal_id=goal_id,
            milestone_id=milestone_id,
            owner_id=user.id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task_data(task)

    def update_task(
        task_id: int,
        title: str = "",
        completed: bool | None = None,
        priority: str | None = None,
        due_date: str | None = None,
        category: str | None = None,
        estimated_minutes: int | None = None,
        goal_id: int | None = None,
        milestone_id: int | None = None,
    ) -> dict:
        """Update an owned task. Never accept or change an owner ID."""
        task = db.scalar(select(Task).where(Task.id == task_id, Task.owner_id == user.id))
        if task is None:
            return {"error": "Task not found"}
        if title:
            task.title = title
        if milestone_id is not None:
            milestone = db.scalar(
                select(Milestone).join(Goal).where(
                    Milestone.id == milestone_id, Goal.owner_id == user.id
                )
            )
            if milestone is None:
                return {"error": "Milestone not found"}
            if goal_id is not None and goal_id != milestone.goal_id:
                return {"error": "Milestone does not belong to goal"}
            goal_id = milestone.goal_id
        elif goal_id is not None and db.scalar(
            select(Goal).where(Goal.id == goal_id, Goal.owner_id == user.id)
        ) is None:
            return {"error": "Goal not found"}
        if goal_id is not None:
            task.goal_id = goal_id
        if milestone_id is not None:
            task.milestone_id = milestone_id
            task.goal_id = goal_id
        elif remove_milestone:
            task.milestone_id = None
        if completed is not None:
            task.completed = completed
        if priority is not None:
            task.priority, _, _ = validate_metadata(priority, None, estimated_minutes)
        if due_date is not None:
            _, task.due_date, _ = validate_metadata(
                task.priority, due_date, estimated_minutes
            )
        if category is not None:
            task.category = category
        if estimated_minutes is not None:
            _, _, task.estimated_minutes = validate_metadata(
                task.priority, None, estimated_minutes
            )
        db.commit()
        return task_data(task)

    def delete_task(task_id: int) -> dict:
        """Delete an owned task."""
        task = db.scalar(select(Task).where(Task.id == task_id, Task.owner_id == user.id))
        if task is None:
            return {"error": "Task not found"}
        db.delete(task)
        db.commit()
        return {"deleted": task_id}

    def list_goals() -> list[dict]:
        """List goals belonging to the authenticated user."""
        return [
            {
                "id": goal.id,
                "title": goal.title,
                "description": goal.description,
                "status": goal.status,
                "progress": goal.progress,
                "target_date": goal.target_date.isoformat() if goal.target_date else None,
            }
            for goal in db.scalars(
                select(Goal).where(Goal.owner_id == user.id).order_by(Goal.created_at.desc())
            )
        ]

    def add_goal(
        title: str,
        description: str = "",
        start_date: str | None = None,
        target_date: str | None = None,
    ) -> dict:
        """Create a goal for the authenticated user."""
        def parse_date(value):
            return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
        goal = Goal(
            title=title,
            description=description or None,
            start_date=parse_date(start_date),
            target_date=parse_date(target_date),
            owner_id=user.id,
        )
        db.add(goal)
        db.commit()
        db.refresh(goal)
        return {"id": goal.id, "title": goal.title, "status": goal.status, "progress": goal.progress}

    def add_milestone(goal_id: int, title: str, due_date: str | None = None) -> dict:
        """Add a milestone only to one of the authenticated user's goals."""
        goal = db.scalar(select(Goal).where(Goal.id == goal_id, Goal.owner_id == user.id))
        if goal is None:
            return {"error": "Goal not found"}
        parsed_date = datetime.fromisoformat(due_date.replace("Z", "+00:00")) if due_date else None
        milestone = Milestone(title=title, due_date=parsed_date, goal_id=goal.id)
        db.add(milestone)
        db.commit()
        db.refresh(milestone)
        return {"id": milestone.id, "goal_id": goal.id, "title": milestone.title, "status": milestone.status}

    def list_milestones(goal_id: int) -> list[dict]:
        """List milestones for an owned goal."""
        return [
            {"id": milestone.id, "goal_id": goal_id, "title": milestone.title,
             "status": milestone.status, "task_ids": [task.id for task in milestone.tasks]}
            for milestone in db.scalars(
                select(Milestone).join(Goal).where(
                    Milestone.goal_id == goal_id, Goal.owner_id == user.id
                )
            )
        ]

    return [
        list_tasks, add_task, update_task, delete_task, list_goals, add_goal,
        add_milestone, list_milestones
    ]


async def generate_goal_breakdown(goal: Goal, db: Session, user: User) -> BreakdownProposal:
    if not GOOGLE_API_KEY:
        raise RuntimeError("AI assistant is not configured")
    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner

    prompt = f"""
Create a practical breakdown for this goal:
Title: {goal.title}
Description: {goal.description or "No additional description"}
Start date: {goal.start_date or "today"}
Target date: {goal.target_date or "not specified"}

Return ONLY valid JSON with this shape:
{{"summary":"short explanation","milestones":[{{"title":"...","description":"...","due_date":"ISO datetime or null"}}],"tasks":[{{"title":"...","description":"...","priority":"low|medium|high|urgent","due_date":"ISO datetime or null","estimated_minutes":30,"milestone_index":0}}]}}
Make the milestones achievable and the tasks small. Do not include user IDs.
"""
    last_error = None
    for model in dict.fromkeys((GEMINI_MODEL, GEMINI_FALLBACK_MODEL)):
        try:
            agent = LlmAgent(
                name="goal_breakdown_assistant",
                model=model,
                instruction="Return only the requested JSON. Do not call tools.",
                mode="chat",
            )
            runner = InMemoryRunner(agent=agent, app_name="task-assistant")
            events = await runner.run_debug(
                prompt, user_id=str(user.id), session_id=f"goal-breakdown-{goal.id}"
            )
            text = extract_final_text(events)
            if not text:
                raise RuntimeError("AI provider returned no breakdown")
            cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
            return BreakdownProposal.model_validate(json.loads(cleaned))
        except Exception as error:
            last_error = error
            logger.warning("Goal breakdown model %s failed: %s", model, error)
            await asyncio.sleep(1)
    raise RuntimeError("The AI service could not create a goal breakdown") from last_error


async def generate_reply(message: str, db: Session, user: User, session_id: str) -> str:
    if not GOOGLE_API_KEY:
        raise RuntimeError("AI assistant is not configured")
    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner

    last_error = None
    for model in dict.fromkeys((GEMINI_MODEL, GEMINI_FALLBACK_MODEL)):
        try:
            agent = LlmAgent(
                name="task_assistant",
                model=model,
                instruction=(
                    "You are a concise task-management assistant. Use tools for task operations. "
                    "Only operate on the authenticated user's tasks. Never ask for or invent user IDs."
                ),
                tools=build_tools(db, user),
                mode="chat",
            )
            runner = InMemoryRunner(agent=agent, app_name="task-assistant")
            events = await runner.run_debug(
                message, user_id=str(user.id), session_id=f"conversation-{session_id}"
            )
            break
        except Exception as error:
            last_error = error
            logger.warning("AI model %s failed: %s", model, error)
            await asyncio.sleep(1)
    else:
        raise RuntimeError(
            "The AI service is temporarily unavailable. "
            "Please try again in a moment."
        ) from last_error
    logger.info("ADK returned %d events for conversation %s", len(events), session_id)
    reply = extract_final_text(events)
    if reply:
        return reply
    logger.error(
        "ADK returned no assistant text for conversation %s; event_types=%s",
        session_id,
        [
            [
                "text" if getattr(part, "text", None) else
                "function_call" if getattr(part, "function_call", None) else
                "function_response" if getattr(part, "function_response", None) else
                "other"
                for part in (getattr(getattr(event, "content", None), "parts", []) or [])
            ]
            for event in events
        ],
    )
    raise RuntimeError("AI provider returned no assistant response")
