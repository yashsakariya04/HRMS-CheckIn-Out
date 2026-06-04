from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Task snapshot shown inside a group ───────────────────────────────────────

class TaskSnapshotInGroup(BaseModel):
    task_id: uuid.UUID
    title: str
    status: str
    priority: str
    deadline: Optional[datetime]
    created_by: uuid.UUID
    creator_name: Optional[str]
    similarity_score: Optional[float]
    role: str  # candidate | primary | merged


# ── Merge request schemas ─────────────────────────────────────────────────────

class MergeRequestCreate(BaseModel):
    """Body for POST /tracker/duplicates/{group_id}/merge-request"""
    primary_task_id: uuid.UUID
    reason: str = Field(..., min_length=10, max_length=1000)


class MergeRequestReview(BaseModel):
    """Body for POST /tracker/duplicates/merge-requests/{id}/approve|reject"""
    action: Literal["approve", "reject"]
    note: Optional[str] = Field(None, max_length=500)


class MergeRequestResponse(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    requested_by: uuid.UUID
    requester_name: Optional[str]
    primary_task_id: uuid.UUID
    reason: str
    status: str  # pending | approved | rejected
    reviewed_by: Optional[uuid.UUID]
    reviewer_name: Optional[str]
    review_note: Optional[str]
    created_at: datetime
    reviewed_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ── Duplicate group response ──────────────────────────────────────────────────

class DuplicateGroupResponse(BaseModel):
    id: uuid.UUID
    developer_id: uuid.UUID
    label: Optional[str]
    status: str  # open | kept | merge_requested | merged | rejected
    tasks: list[TaskSnapshotInGroup]
    merge_request: Optional[MergeRequestResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
