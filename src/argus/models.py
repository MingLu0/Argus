from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
    AWAITING_DECISION = "awaiting_decision"
    CANCELLED = "cancelled"


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    AWAITING_DECISION = "awaiting_decision"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackendStatus(BaseModel):
    id: str
    binary: str
    available: bool
    path: str | None = None
    reason: str | None = None


class BackendResult(BaseModel):
    backend_id: str
    reviewer_id: str
    command: list[str]
    exit_code: int | None
    stdout: str
    stderr: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    timed_out: bool = False


class BackendInvocation(BaseModel):
    backend_id: str
    command: list[str]
    input_text: str


class ReviewerRecord(BaseModel):
    id: str
    role: str
    backend: str
    status: StepStatus = StepStatus.PENDING
    command: list[str] = Field(default_factory=list)
    duration_ms: int | None = None
    exit_code: int | None = None
    timed_out: bool = False
    error: str | None = None
    artifacts: list[str] = Field(default_factory=list)


class StepRecord(BaseModel):
    id: str
    name: str
    status: StepStatus = StepStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    error: str | None = None
    artifacts: list[str] = Field(default_factory=list)


class RunManifest(BaseModel):
    id: str
    title: str
    mode: str
    status: RunStatus
    topic_path: str
    created_at: datetime
    updated_at: datetime
    steps: list[StepRecord] = Field(default_factory=list)


class ReviewerSpec(BaseModel):
    id: str
    role: str
    backend: str


class RunContext(BaseModel):
    project_root: Path
    run_dir: Path
    manifest: RunManifest


def utc_now() -> datetime:
    return datetime.now(UTC)
