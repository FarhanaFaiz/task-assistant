from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import Goal, Milestone, Task, User
from app.schemas.tasks import Priority, TaskCreate, TaskResponse, TaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def owned_task(task_id: int, user: User, db: Session) -> Task:
    task = db.scalar(select(Task).where(Task.id == task_id, Task.owner_id == user.id))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def resolve_task_links(
    goal_id: int | None,
    milestone_id: int | None,
    user: User,
    db: Session,
) -> tuple[int | None, int | None]:
    if milestone_id is None:
        if goal_id is not None and db.scalar(
            select(Goal).where(Goal.id == goal_id, Goal.owner_id == user.id)
        ) is None:
            raise HTTPException(status_code=404, detail="Goal not found")
        return goal_id, None
    milestone = db.scalar(
        select(Milestone)
        .join(Goal)
        .where(
            Milestone.id == milestone_id,
            Goal.owner_id == user.id,
        )
    )
    if milestone is None:
        raise HTTPException(status_code=404, detail="Milestone not found")
    if goal_id is not None and goal_id != milestone.goal_id:
        raise HTTPException(
            status_code=400,
            detail="Milestone does not belong to the selected goal",
        )
    return milestone.goal_id, milestone.id


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    goal_id, milestone_id = resolve_task_links(
        payload.goal_id, payload.milestone_id, user, db
    )
    values = payload.model_dump(exclude={"goal_id", "milestone_id"})
    task = Task(**values, goal_id=goal_id, milestone_id=milestone_id, owner_id=user.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    priority: Priority | None = Query(default=None),
    category: str | None = Query(default=None, max_length=100),
    completed: bool | None = None,
    sort: str = Query(default="created", pattern="^(created|due_date|priority)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Task).where(Task.owner_id == user.id)
    if priority:
        query = query.where(Task.priority == priority)
    if category:
        query = query.where(Task.category == category)
    if completed is not None:
        query = query.where(Task.completed == completed)
    if sort == "due_date":
        ordering = (Task.due_date.is_(None), Task.due_date.asc(), Task.created_at.desc())
    elif sort == "priority":
        priority_order = case(
            (Task.priority == "urgent", 0),
            (Task.priority == "high", 1),
            (Task.priority == "medium", 2),
            else_=3,
        )
        ordering = (priority_order, Task.created_at.desc())
    else:
        ordering = (Task.created_at.desc(),)
    return list(db.scalars(query.order_by(*ordering)))


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return owned_task(task_id, user, db)


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, payload: TaskUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = owned_task(task_id, user, db)
    values = payload.model_dump(exclude_unset=True)
    goal_id = values.pop("goal_id", task.goal_id)
    milestone_id = values.pop("milestone_id", task.milestone_id)
    goal_id, milestone_id = resolve_task_links(goal_id, milestone_id, user, db)
    for key, value in values.items():
        setattr(task, key, value)
    task.goal_id = goal_id
    task.milestone_id = milestone_id
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = owned_task(task_id, user, db)
    db.delete(task)
    db.commit()
