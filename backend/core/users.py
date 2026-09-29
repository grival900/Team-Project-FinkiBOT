"""Checks for admin user management (e.g. don't remove the last admin). They take plain
values so they can be tested without a database."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import User


class SelfActionError(Exception):
    """An admin tried to demote/deactivate/delete their own account."""


class LastAdminError(Exception):
    """An action would leave zero active admins."""


def guard_not_self(target_id: UUID, current_id: UUID) -> None:
    if target_id == current_id:
        raise SelfActionError("Cannot perform this action on your own account")


def guard_last_admin(is_currently_active_admin: bool, other_active_admins_count: int) -> None:
    """Call only when the action being guarded would strip the target's active-admin
    status (demote, deactivate, or delete) — blocks it if no other active admin exists."""
    if is_currently_active_admin and other_active_admins_count == 0:
        raise LastAdminError("Cannot remove the last remaining admin")


def count_other_active_admins(db: Session, exclude_user_id: UUID) -> int:
    stmt = select(func.count()).select_from(User).where(
        User.is_admin.is_(True),
        User.is_active.is_(True),
        User.id != exclude_user_id,
    )
    return db.execute(stmt).scalar_one()


def set_admin_status(db: Session, target: User, is_admin: bool) -> User:
    target.is_admin = is_admin
    db.commit()
    db.refresh(target)
    return target


def set_active_status(db: Session, target: User, is_active: bool) -> User:
    target.is_active = is_active
    db.commit()
    db.refresh(target)
    return target


def delete_user(db: Session, target: User) -> None:
    db.delete(target)
    db.commit()
