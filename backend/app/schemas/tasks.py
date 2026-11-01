from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["low", "medium", "high", "urgent"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    priority: Priority = "medium"
    due_date: datetime | None = None
    category: str | None = Field(default=None, max_length=100)
    estimated_minutes: int | None = Field(default=None, gt=0)
    goal_id: int | None = Field(default=None, gt=0)
    milestone_id: int | None = Field(default=None, gt=0)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    completed: bool | None = None
    priority: Priority | None = None
    due_date: datetime | None = None
    category: str | None = Field(default=None, max_length=100)
    estimated_minutes: int | None = Field(default=None, gt=0)
    goal_id: int | None = Field(default=None, gt=0)
    milestone_id: int | None = Field(default=None, gt=0)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    completed: bool
    priority: Priority
    due_date: datetime | None
    category: str | None
    estimated_minutes: int | None
    created_at: datetime
    updated_at: datetime
    owner_id: int
    goal_id: int | None
    milestone_id: int | None
