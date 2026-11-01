from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

GoalStatus = Literal["active", "completed", "paused", "archived"]
MilestoneStatus = Literal["pending", "in_progress", "completed"]


class MilestoneCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    due_date: datetime | None = None
    status: MilestoneStatus = "pending"


class MilestoneUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    due_date: datetime | None = None
    status: MilestoneStatus | None = None


class MilestoneResponse(MilestoneCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    goal_id: int
    created_at: datetime
    updated_at: datetime
    task_ids: list[int] = []
    task_count: int = 0
    tasks: list[dict] = []


class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    start_date: datetime | None = None
    target_date: datetime | None = None
    status: GoalStatus = "active"
    progress: int = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def dates_are_ordered(self):
        if self.start_date and self.target_date and self.target_date < self.start_date:
            raise ValueError("target_date must be on or after start_date")
        return self


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    start_date: datetime | None = None
    target_date: datetime | None = None
    status: GoalStatus | None = None
    progress: int | None = Field(default=None, ge=0, le=100)


class GoalResponse(GoalCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime
    milestones: list[MilestoneResponse] = []
    task_ids: list[int] = []


class BreakdownTask(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    due_date: datetime | None = None
    estimated_minutes: int | None = Field(default=None, gt=0)
    milestone_index: int | None = Field(default=None, ge=0)


class BreakdownMilestone(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    due_date: datetime | None = None


class BreakdownProposal(BaseModel):
    summary: str
    milestones: list[BreakdownMilestone]
    tasks: list[BreakdownTask]


class BreakdownApproval(BaseModel):
    proposal: BreakdownProposal
