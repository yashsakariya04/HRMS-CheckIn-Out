"""
Duplicate task detection and merge-request panel.

Developer endpoints:
  GET  /tracker/duplicates/my-groups                          — load dashboard groups
  POST /tracker/duplicates/{group_id}/keep                    — dismiss group (keep all)
  POST /tracker/duplicates/{group_id}/merge-request           — request merge

Manager endpoints:
  GET  /tracker/duplicates/merge-requests/pending             — list pending requests
  POST /tracker/duplicates/merge-requests/{id}/review         — approve or reject
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, require_admin
from app.dependencies.database import get_db
from app.models.employee import Employee
from app.schemas.tracker.similar_task import (
    DuplicateGroupResponse, MergeRequestCreate,
    MergeRequestResponse, MergeRequestReview,
)
from app.services.tracker import similar_task_service

router = APIRouter(prefix="/tracker/duplicates", tags=["Tracker — Duplicate Detection"])


@router.get("/my-groups", response_model=list[DuplicateGroupResponse])
async def get_my_duplicate_groups(
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Developer dashboard — runs similarity clustering across all assigned active tasks.
    Returns groups of tasks that appear to be duplicates.
    Groups already dismissed (kept/merged/rejected) are not returned.
    """
    return await similar_task_service.get_my_duplicate_groups(db, user)


@router.post("/{group_id}/keep")
async def keep_group(
    group_id: uuid.UUID,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Developer chooses 'Keep All' — these tasks are not duplicates, dismiss the group.
    """
    return await similar_task_service.keep_group(db, group_id, user)


@router.post("/{group_id}/merge-request", response_model=MergeRequestResponse, status_code=201)
async def request_merge(
    group_id: uuid.UUID,
    payload: MergeRequestCreate,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Developer requests to merge duplicate tasks into one primary task.
    All managers (task creators) in the group are notified.
    """
    return await similar_task_service.request_merge(db, group_id, payload, user)


@router.get("/merge-requests/pending", response_model=list[MergeRequestResponse])
async def get_pending_merge_requests(
    manager: Employee = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Manager panel — list all pending merge requests in the organisation.
    """
    return await similar_task_service.get_pending_merge_requests(db, manager)


@router.post("/merge-requests/{request_id}/review", response_model=MergeRequestResponse)
async def review_merge_request(
    request_id: uuid.UUID,
    payload: MergeRequestReview,
    manager: Employee = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Manager approves or rejects a merge request.
    - approve: primary task stays active, all other tasks in the group are closed (rejected)
    - reject: developer continues working on all tasks
    """
    return await similar_task_service.review_merge_request(db, request_id, payload, manager)
