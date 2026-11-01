from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agent.service import generate_goal_breakdown
from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import Goal, Milestone, Task, User
from app.schemas.goals import (
    BreakdownApproval,
    BreakdownProposal,
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    MilestoneCreate,
    MilestoneResponse,
    MilestoneUpdate,
)

router = APIRouter(prefix="/api/goals", tags=["goals"])


def owned_goal(goal_id: int, user: User, db: Session) -> Goal:
    goal = db.scalar(
        select(Goal)
        .options(selectinload(Goal.milestones), selectinload(Goal.tasks))
        .where(Goal.id == goal_id, Goal.owner_id == user.id)
    )
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


def goal_response(goal: Goal) -> GoalResponse:
    milestones = [
        {
            **{key: getattr(item, key) for key in (
                "id", "title", "description", "due_date", "status",
                "goal_id", "created_at", "updated_at"
            )},
            "task_ids": [task.id for task in item.tasks],
            "task_count": len(item.tasks),
            "tasks": [
                {
                    "id": task.id,
                    "title": task.title,
                    "completed": task.completed,
                    "priority": task.priority,
                    "goal_id": task.goal_id,
                    "milestone_id": task.milestone_id,
                }
                for task in item.tasks
            ],
        }
        for item in goal.milestones
    ]
    return GoalResponse(
        **{key: getattr(goal, key) for key in (
            "id", "title", "description", "start_date", "target_date",
            "status", "progress", "owner_id", "created_at", "updated_at"
        )},
        milestones=milestones,
        task_ids=[task.id for task in goal.tasks],
    )


def refresh_progress(goal: Goal) -> None:
    if goal.milestones:
        goal.progress = round(
            sum(item.status == "completed" for item in goal.milestones)
            / len(goal.milestones)
            * 100
        )


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(payload: GoalCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    goal = Goal(**payload.model_dump(), owner_id=user.id)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    goal.milestones = []
    goal.tasks = []
    return goal_response(goal)


@router.get("", response_model=list[GoalResponse])
def list_goals(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    goals = db.scalars(
        select(Goal)
        .options(selectinload(Goal.milestones), selectinload(Goal.tasks))
        .where(Goal.owner_id == user.id)
        .order_by(Goal.created_at.desc())
    ).all()
    return [goal_response(goal) for goal in goals]


@router.get("/{goal_id}", response_model=GoalResponse)
def get_goal(goal_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return goal_response(owned_goal(goal_id, user, db))


@router.patch("/{goal_id}", response_model=GoalResponse)
def update_goal(goal_id: int, payload: GoalUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    goal = owned_goal(goal_id, user, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, key, value)
    db.commit()
    db.refresh(goal)
    return goal_response(owned_goal(goal_id, user, db))


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    goal = owned_goal(goal_id, user, db)
    db.delete(goal)
    db.commit()


@router.post("/{goal_id}/milestones", response_model=MilestoneResponse, status_code=status.HTTP_201_CREATED)
def create_milestone(goal_id: int, payload: MilestoneCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_goal(goal_id, user, db)
    milestone = Milestone(**payload.model_dump(), goal_id=goal_id)
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.patch("/{goal_id}/milestones/{milestone_id}", response_model=MilestoneResponse)
def update_milestone(goal_id: int, milestone_id: int, payload: MilestoneUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_goal(goal_id, user, db)
    milestone = db.scalar(
        select(Milestone).join(Goal).where(
            Milestone.id == milestone_id, Milestone.goal_id == goal_id, Goal.owner_id == user.id
        )
    )
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(milestone, key, value)
    goal = owned_goal(goal_id, user, db)
    refresh_progress(goal)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.delete("/{goal_id}/milestones/{milestone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_milestone(goal_id: int, milestone_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_goal(goal_id, user, db)
    milestone = db.scalar(
        select(Milestone).join(Goal).where(
            Milestone.id == milestone_id, Milestone.goal_id == goal_id, Goal.owner_id == user.id
        )
    )
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found")
    db.delete(milestone)
    db.commit()


@router.post("/{goal_id}/breakdown", response_model=BreakdownProposal)
async def breakdown_goal(goal_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    goal = owned_goal(goal_id, user, db)
    try:
        return await generate_goal_breakdown(goal, db, user)
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"AI assistant unavailable: {error}") from error


@router.post("/{goal_id}/breakdown/approve", response_model=GoalResponse)
def approve_breakdown(goal_id: int, payload: BreakdownApproval, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    goal = owned_goal(goal_id, user, db)
    milestones = [
        Milestone(
            title=item.title, description=item.description, due_date=item.due_date, goal_id=goal.id
        )
        for item in payload.proposal.milestones
    ]
    db.add_all(milestones)
    db.flush()
    for item in payload.proposal.tasks:
        db.add(Task(
            title=item.title, description=item.description, priority=item.priority,
            due_date=item.due_date, estimated_minutes=item.estimated_minutes,
            category="Goal", owner_id=user.id, goal_id=goal.id,
            milestone_id=(
                milestones[item.milestone_index].id
                if item.milestone_index is not None
                and 0 <= item.milestone_index < len(milestones)
                else None
            ),
        ))
    db.commit()
    return goal_response(owned_goal(goal_id, user, db))
