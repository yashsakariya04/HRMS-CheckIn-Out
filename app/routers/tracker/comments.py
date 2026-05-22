import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.employee import Employee
from app.schemas.tracker.comment import CommentCreate, CommentResponse
from app.services.tracker import comment_service

router = APIRouter(prefix="/tracker/tasks/{task_id}/comments", tags=["Tracker — Comments"])


@router.post("", response_model=CommentResponse, status_code=201)
async def add_comment(
    task_id: uuid.UUID,
    payload: CommentCreate,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    comment = await comment_service.add_comment(db, task_id, payload, user)
    # Enrich author name
    r = await db.execute(select(Employee).where(Employee.id == comment.user_id))
    emp = r.scalars().first()
    return CommentResponse(
        id=comment.id,
        task_id=comment.task_id,
        user_id=comment.user_id,
        author_name=emp.full_name or emp.email if emp else None,
        message=comment.message,
        created_at=comment.created_at,
    )


@router.get("", response_model=list[CommentResponse])
async def list_comments(
    task_id: uuid.UUID,
    user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    comments = await comment_service.get_comments(db, task_id, user.organization_id)
    out = []
    for c in comments:
        r = await db.execute(select(Employee).where(Employee.id == c.user_id))
        emp = r.scalars().first()
        out.append(CommentResponse(
            id=c.id,
            task_id=c.task_id,
            user_id=c.user_id,
            author_name=emp.full_name or emp.email if emp else None,
            message=c.message,
            created_at=c.created_at,
        ))
    return out
