import uuid
from datetime import datetime
from typing import Any, Dict, List, AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import get_current_user, require_staff, enforce_owner_or_staff
from app.database import Base, engine, get_db
from app.models import CreditLedger, CreditPack, FitnessClass, Reservation, Studio, User
from app.schemas import (
    BalanceReport, BookingRequest, BookingResponse, ClassCreate, ClassResponse,
    CreditPackGrant, LedgerEntrySchema, ReservationResponse, StudioCreate, StudioResponse,
    UserCreate, UserResponse
)
from app.services import BookingService, LedgerService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Studio Booking Platform Engine", version="2.0.0", lifespan=lifespan)


@app.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    user = User(email=payload.email, name=payload.name, is_staff=payload.is_staff)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@app.post("/studios", response_model=StudioResponse, status_code=status.HTTP_201_CREATED)
async def create_studio(payload: StudioCreate, db: AsyncSession = Depends(get_db),
                        current_user: User = Depends(require_staff)) -> Studio:
    studio = Studio(name=payload.name, timezone=payload.timezone,
                    cancellation_cutoff_hours=payload.cancellation_cutoff_hours)
    db.add(studio)
    await db.commit()
    await db.refresh(studio)
    return studio


@app.post("/studios/{studio_id}/classes", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
async def schedule_class(studio_id: uuid.UUID, payload: ClassCreate, db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(require_staff)) -> FitnessClass:
    studio = await db.get(Studio, studio_id)
    if not studio:
        raise HTTPException(status_code=404, detail="Target Studio configuration not found")

    fitness_class = FitnessClass(
        studio_id=studio_id, name=payload.name, instructor=payload.instructor,
        start_time=payload.start_time, total_capacity=payload.total_capacity, available_spots=payload.total_capacity
    )
    db.add(fitness_class)
    await db.commit()
    await db.refresh(fitness_class)
    return fitness_class


@app.get("/classes", response_model=List[ClassResponse], status_code=status.HTTP_200_OK)
async def browse_classes(start: datetime = Query(...), end: datetime = Query(...),
                         db: AsyncSession = Depends(get_db)) -> Any:
    query = select(FitnessClass).where(FitnessClass.start_time >= start, FitnessClass.start_time <= end)
    res = await db.execute(query)
    return res.scalars().all()


@app.post("/users/{user_id}/credit-packs", status_code=status.HTTP_201_CREATED)
async def grant_credit_pack(user_id: uuid.UUID, payload: CreditPackGrant, db: AsyncSession = Depends(get_db),
                            current_user: User = Depends(require_staff)) -> Dict[str, Any]:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User target missing")

    async with db.begin():
        pack = CreditPack(user_id=user_id, total_credits=payload.total_credits, expiry_date=payload.expiry_date)
        db.add(pack)
        await db.flush()

        ledger = CreditLedger(user_id=user_id, credit_pack_id=pack.id, amount=payload.total_credits,
                              action_type="GRANT")
        db.add(ledger)

    return {"status": "granted", "pack_id": pack.id}


@app.get("/users/{user_id}/credits/balance", response_model=BalanceReport)
async def get_credits_balance(user_id: uuid.UUID, point_in_time: datetime | None = Query(default=None),
                              db: AsyncSession = Depends(get_db),
                              current_user: User = Depends(get_current_user)) -> Any:
    enforce_owner_or_staff(user_id, current_user)
    return await LedgerService.get_balance_report(db, user_id, point_in_time)


@app.get("/users/{user_id}/credits/statement", response_model=List[LedgerEntrySchema])
async def get_ledger_statement(user_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                               current_user: User = Depends(get_current_user)) -> Any:
    enforce_owner_or_staff(user_id, current_user)
    query = select(CreditLedger).where(CreditLedger.user_id == user_id).order_by(CreditLedger.created_at.desc())
    res = await db.execute(query)
    return res.scalars().all()


@app.post("/bookings", response_model=BookingResponse)
async def book_class(payload: BookingRequest, db: AsyncSession = Depends(get_db),
                     current_user: User = Depends(get_current_user)) -> Any:
    async with db.begin():
        reservation, msg = await BookingService.book_class(db, current_user.id, payload.class_id)
        return BookingResponse(reservation_id=reservation.id, class_id=reservation.class_id, status=reservation.status,
                               message=msg)


@app.get("/users/{user_id}/bookings", response_model=List[ReservationResponse])
async def list_user_bookings(user_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                             current_user: User = Depends(get_current_user)) -> Any:
    enforce_owner_or_staff(user_id, current_user)
    query = select(Reservation).where(Reservation.user_id == user_id).order_by(Reservation.created_at.desc())
    res = await db.execute(query)
    return res.scalars().all()


@app.delete("/bookings/{reservation_id}")
async def cancel_booking(reservation_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(get_current_user)) -> Dict[str, str]:
    async with db.begin():
        return await BookingService.cancel_booking(db, current_user.id, reservation_id)
