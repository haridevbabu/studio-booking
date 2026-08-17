import uuid
from fastapi import Header, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User


async def get_current_user(
        x_user_id: str = Header(..., description="Simulated Auth Header via User ID UUID"),
        db: AsyncSession = Depends(get_db)
) -> User:
    try:
        user_uuid = uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Security Token Format")

    user = await db.get(User, user_uuid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User Identity Not Found")
    return user


def require_staff(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_staff:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff privileges required")
    return current_user


def enforce_owner_or_staff(target_user_id: uuid.UUID, current_user: User) -> None:
    if not current_user.is_staff and current_user.id != target_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Access Denied: Resource belongs to another user")
