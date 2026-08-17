import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)

    credit_packs: Mapped[list["CreditPack"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    ledger_entries: Mapped[list["CreditLedger"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Studio(Base):
    __tablename__ = "studios"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    cancellation_cutoff_hours: Mapped[int] = mapped_column(Integer, default=12)

    fitness_classes: Mapped[list["FitnessClass"]] = relationship(back_populates="studio", cascade="all, delete-orphan")


class FitnessClass(Base):
    __tablename__ = "fitness_classes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    studio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("studios.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    instructor: Mapped[str] = mapped_column(String(100))
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    total_capacity: Mapped[int] = mapped_column(Integer)
    available_spots: Mapped[int] = mapped_column(Integer)

    studio: Mapped["Studio"] = relationship(back_populates="fitness_classes")
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="fitness_class", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("available_spots >= 0", name="check_spots_non_negative"),
    )


class CreditPack(Base):
    __tablename__ = "credit_packs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    total_credits: Mapped[int] = mapped_column(Integer)
    expiry_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="credit_packs")
    ledger_entries: Mapped[list["CreditLedger"]] = relationship(back_populates="credit_pack", cascade="all, delete-orphan")


class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    credit_pack_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("credit_packs.id", ondelete="SET NULL"), nullable=True)
    amount: Mapped[int] = mapped_column(Integer)  # Negative for debits, Positive for credits
    action_type: Mapped[str] = mapped_column(String(50))  # GRANT, BOOKING, CANCEL_REFUND
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user: Mapped["User"] = relationship(back_populates="ledger_entries")
    credit_pack: Mapped["CreditPack"] = relationship(back_populates="ledger_entries")


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fitness_classes.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="CONFIRMED")  # CONFIRMED, WAITLISTED, CANCELLED, WAITLIST_LEFT
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    fitness_class: Mapped["FitnessClass"] = relationship(back_populates="reservations")
    user: Mapped["User"] = relationship(back_populates="reservations")