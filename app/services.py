import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import CreditLedger, CreditPack, FitnessClass, Reservation, Studio


class LedgerService:
    @staticmethod
    async def get_balance_report(db: AsyncSession, user_id: uuid.UUID, point_in_time: datetime | None = None) -> Dict[
        str, Any]:
        target_time = point_in_time or datetime.now(timezone.utc)
        if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=timezone.utc)

        packs_query = select(CreditPack).where(
            CreditPack.user_id == user_id,
            CreditPack.created_at <= target_time
        ).order_by(CreditPack.expiry_date.asc())
        packs_res = await db.execute(packs_query)
        all_packs = packs_res.scalars().all()

        breakdown: List[Dict[str, Any]] = []
        total_balance = 0

        for pack in all_packs:
            mv_query = select(func.coalesce(func.sum(CreditLedger.amount), 0)).where(
                CreditLedger.credit_pack_id == pack.id,
                CreditLedger.created_at <= target_time
            )
            mv_res = await db.execute(mv_query)
            pack_balance = int(mv_res.scalar_one())

            pack_expiry = pack.expiry_date.replace(
                tzinfo=timezone.utc) if pack.expiry_date.tzinfo is None else pack.expiry_date

            if pack_expiry > target_time and pack_balance > 0:
                breakdown.append({
                    "pack_id": pack.id,
                    "initial_credits": pack.total_credits,
                    "remaining_credits": pack_balance,
                    "expiry_date": pack.expiry_date
                })
                total_balance += pack_balance

        return {"current_balance": max(0, total_balance), "active_breakdown": breakdown}

    @staticmethod
    async def consume_credits_fifo(db: AsyncSession, user_id: uuid.UUID, total_cost: int,
                                   reservation_id: uuid.UUID) -> None:
        now = datetime.now(timezone.utc)

        packs_query = select(CreditPack).where(
            CreditPack.user_id == user_id,
            CreditPack.expiry_date > now
        ).order_by(CreditPack.expiry_date.asc()).with_for_update()

        packs_res = await db.execute(packs_query)
        active_packs = packs_res.scalars().all()

        credits_left_to_deduct = total_cost

        report = await LedgerService.get_balance_report(db, user_id, now)
        if report["current_balance"] < total_cost:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Insufficient credits to purchase class.")

        for pack in active_packs:
            if credits_left_to_deduct <= 0:
                break

            sum_query = select(func.coalesce(func.sum(CreditLedger.amount), 0)).where(
                CreditLedger.credit_pack_id == pack.id
            ).with_for_update()
            sum_res = await db.execute(sum_query)
            current_pack_bal = int(sum_res.scalar_one())

            if current_pack_bal > 0:
                deduction = min(current_pack_bal, credits_left_to_deduct)
                ledger = CreditLedger(
                    user_id=user_id,
                    credit_pack_id=pack.id,
                    reservation_id=reservation_id,
                    amount=-deduction,
                    action_type="BOOKING"
                )
                db.add(ledger)
                credits_left_to_deduct -= deduction

        if credits_left_to_deduct > 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credit deduction processing failure.")


class BookingService:
    @staticmethod
    async def book_class(db: AsyncSession, user_id: uuid.UUID, class_id: uuid.UUID) -> Tuple[Reservation, str]:
        class_query = select(FitnessClass).where(FitnessClass.id == class_id).with_for_update()
        class_res = await db.execute(class_query)
        fitness_class = class_res.scalar_one_or_none()
        if not fitness_class:
            raise HTTPException(status_code=404, detail="Class not found")

        dup_query = select(Reservation).where(
            Reservation.class_id == class_id,
            Reservation.user_id == user_id,
            Reservation.status.in_(["CONFIRMED", "WAITLISTED"])
        )
        dup_res = await db.execute(dup_query)
        if dup_res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Duplicate registration entry detected")

        # Validate total liquidity before reserving spot
        now = datetime.now(timezone.utc)
        report = await LedgerService.get_balance_report(db, user_id, now)
        if report["current_balance"] < fitness_class.credit_cost:
            raise HTTPException(status_code=400, detail="Insufficient credits for booking.")

        if fitness_class.available_spots > 0:
            fitness_class.available_spots -= 1
            res_status = "CONFIRMED"
            msg = "Spot confirmed successfully."
        else:
            res_status = "WAITLISTED"
            msg = "Class full. Assigned to waitlist queue."

        reservation = Reservation(class_id=class_id, user_id=user_id, status=res_status)
        db.add(reservation)
        await db.flush()
        await LedgerService.consume_credits_fifo(db, user_id, fitness_class.credit_cost, reservation.id)
        return reservation, msg

    @staticmethod
    async def cancel_booking(db: AsyncSession, user_id: uuid.UUID, reservation_id: uuid.UUID) -> Dict[str, str]:
        res_query = select(Reservation).where(Reservation.id == reservation_id).with_for_update()
        res_exec = await db.execute(res_query)
        reservation = res_exec.scalar_one_or_none()

        if not reservation or reservation.status in ["CANCELLED", "WAITLIST_LEFT"]:
            raise HTTPException(status_code=404, detail="Active reservation context missing or already cancelled.")

        if reservation.user_id != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized action context mapping")

        class_query = select(FitnessClass).where(FitnessClass.id == reservation.class_id).with_for_update()
        class_exec = await db.execute(class_query)
        fitness_class = class_exec.scalar_one()

        studio = await db.get(Studio, fitness_class.studio_id)

        studio_tz = ZoneInfo(studio.timezone)
        now_local = datetime.now(timezone.utc).astimezone(studio_tz)
        class_start_local = fitness_class.start_time.replace(tzinfo=timezone.utc).astimezone(studio_tz)

        time_diff_hours = (class_start_local - now_local).total_seconds() / 3600
        is_late_cancel = time_diff_hours < studio.cancellation_cutoff_hours

        was_confirmed = reservation.status == "CONFIRMED"

        if reservation.status == "WAITLISTED":
            reservation.status = "WAITLIST_LEFT"
            await BookingService._refund_reservation_credits(db, user_id, reservation.id)
            return {"status": "success", "message": "Left waitlist. Credits returned."}

        reservation.status = "CANCELLED"

        if was_confirmed:
            fitness_class.available_spots += 1
            if not is_late_cancel:
                await BookingService._refund_reservation_credits(db, user_id, reservation.id)
                await BookingService._promote_waitlist(db, fitness_class.id)
                return {"status": "success", "message": "Early cancellation processed. Credit returned."}
            else:
                await BookingService._promote_waitlist(db, fitness_class.id)
                return {"status": "success", "message": "Late cancellation processed. Credit forfeited."}

        return {"status": "success", "message": "Operation completed."}

    @staticmethod
    async def _refund_reservation_credits(db: AsyncSession, user_id: uuid.UUID, reservation_id: uuid.UUID) -> None:
        stmt = select(CreditLedger).where(
            CreditLedger.reservation_id == reservation_id,
            CreditLedger.action_type == "BOOKING"
        )
        res = await db.execute(stmt)
        for entry in res.scalars().all():
            db.add(CreditLedger(
                user_id=user_id,
                credit_pack_id=entry.credit_pack_id,
                reservation_id=reservation_id,
                amount=abs(entry.amount),
                action_type="CANCEL_REFUND"
            ))

    @staticmethod
    async def _promote_waitlist(db: AsyncSession, class_id: uuid.UUID) -> None:
        class_query = select(FitnessClass).where(FitnessClass.id == class_id).with_for_update()
        class_exec = await db.execute(class_query)
        fitness_class = class_exec.scalar_one()

        if fitness_class.available_spots <= 0:
            return

        waitlist_query = select(Reservation).where(
            Reservation.class_id == class_id,
            Reservation.status == "WAITLISTED"
        ).order_by(Reservation.created_at.asc()).with_for_update()

        wait_res = await db.execute(waitlist_query)
        for reservation in wait_res.scalars().all():
            if fitness_class.available_spots <= 0:
                break
