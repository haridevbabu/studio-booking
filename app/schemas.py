import uuid
from datetime import datetime
import zoneinfo
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    is_staff: bool = False


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    name: str
    is_staff: bool


class StudioCreate(BaseModel):
    name: str
    timezone: str = "UTC"
    cancellation_cutoff_hours: int = Field(default=4, ge=0)

    @field_validator("timezone")
    @classmethod
    def validate_iana_timezone(cls, v: str) -> str:
        try:
            zoneinfo.ZoneInfo(v)
        except zoneinfo.ZoneInfoNotFoundError:
            raise ValueError(f"'{v}' is not a recognized, valid IANA timezone identifier.")
        return v


class StudioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    timezone: str
    cancellation_cutoff_hours: int


class ClassCreate(BaseModel):
    name: str
    instructor: str
    start_time: datetime
    duration_minutes: int = Field(default=60, gt=0)
    total_capacity: int = Field(gt=0)
    credit_cost: int = Field(default=1, ge=0)

    @field_validator("start_time")
    @classmethod
    def ensure_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Class start time must contain explicit timezone offsets.")
        return v


class ClassResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    studio_id: uuid.UUID
    name: str
    instructor: str
    start_time: datetime
    duration_minutes: int
    total_capacity: int
    available_spots: int
    credit_cost: int


class CreditPackGrant(BaseModel):
    total_credits: int = Field(gt=0)
    expiry_date: datetime

    @field_validator("expiry_date")
    @classmethod
    def ensure_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Expiry date must contain explicit timezone offsets.")
        return v


class ActivePackSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pack_id: uuid.UUID
    initial_credits: int
    remaining_credits: int
    expiry_date: datetime


class BalanceReport(BaseModel):
    current_balance: int
    active_breakdown: list[ActivePackSchema]


class LedgerEntrySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    credit_pack_id: uuid.UUID | None
    reservation_id: uuid.UUID | None
    amount: int
    action_type: str
    created_at: datetime


class BookingRequest(BaseModel):
    class_id: uuid.UUID


class BookingResponse(BaseModel):
    reservation_id: uuid.UUID
    class_id: uuid.UUID
    status: str
    message: str


class ReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    class_id: uuid.UUID
    status: str
    created_at: datetime
