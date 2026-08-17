import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


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
    cancellation_cutoff_hours: int = Field(default=12, ge=0)


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
    total_capacity: int = Field(gt=0)


class ClassResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    studio_id: uuid.UUID
    name: str
    instructor: str
    start_time: datetime
    total_capacity: int
    available_spots: int


class CreditPackGrant(BaseModel):
    total_credits: int = Field(gt=0)
    expiry_date: datetime


class ActivePackSchema(BaseModel):
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
