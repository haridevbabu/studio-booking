import uuid
from datetime import datetime
from typing import Any, Dict, List, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import CreditLedger, CreditPack, FitnessClass, Reservation, Studio


class LedgerService:
    @staticmethod
    async def get_balance_report(db: AsyncSession, user_id: uuid.UUID, point_in_time: datetime | None = None) -> Dict[
        str, Any]:
        target_time = point_in_time or datetime.utcnow()

        # Fetch all packs granted before or equal to target_time
        packs_query = select(CreditPack).where(
            CreditPack.user_id == user_id,
            CreditPack.created_at <= target_time
        ).order_by(CreditPack.expiry_date.asc())
        packs_res = await db.execute(packs_query)
        all_packs = packs_res.scalars().all()

        breakdown: List[Dict[str, Any]] = []
        total_balance = 0

        for pack in all_packs:
            # Aggregate all movements for this pack up to target_time
            mv_query = select(func.coalesce(func.sum(CreditLedger.amount), 0)).where(
                CreditLedger.credit_pack_id == pack.id,
                CreditLedger.created_at <= target_time
            )
            mv_res = await db.execute(mv_query)
            pack_balance = int(mv_res.scalar_one())

            # Evaluate if pack is expired relative to the targeted moment
            if pack.expiry_date > target_time and pack_balance > 0:
                breakdown.append({
                    "pack_id": pack.id,
                    "initial_credits": pack.total_credits,
                    "remaining_credits": pack_balance,
                    "expiry_date": pack.expiry_date
                })
                total_balance += pack_balance
            elif pack_balance > 0:
                # Expired but had remaining credits at this historical juncture
                total_balance += 0

        return {"current_balance": max(0, total_balance), "active_breakdown": breakdown}

    @staticmethod
    async def consume_credit_atomic(db: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
        now = datetime.utcnow()
        packs_query = select(CreditPack).where(
            CreditPack.user_id == user_id,
            CreditPack.expiry_date > now
        ).order_by(CreditPack.expiry_date.asc())
        packs_res = await db.execute(packs_query)
        active_packs = packs_res.scalars().all()

        for pack in active_packs:
            sum_query = select(func.coalesce(func.sum(CreditLedger.amount), 0)).where(
                CreditLedger.credit_pack_id == pack.id
            )
            sum_res = await db.execute(sum_query)
            current_pack_bal = int(sum_res.scalar_one())

            if current_pack_bal > 0:
                ledger = CreditLedger(
                    user_id=user_id,
                    credit_pack_id=pack.id,
                    amount=-1,
                    action_type="BOOKING",
                    created_at=now
                )
                db.add(ledger)
                return pack.id

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active valid credits found")


class BookingService:
    @staticmethod
    async def book_class(db: AsyncSession, user_id: uuid.UUID, class_id: uuid.UUID) -> Tuple[Reservation, str]:
        # Lock class row
        class_query = select(FitnessClass).where(FitnessClass.id == class_id).with_for_update()
        class_res = await db.execute(class_query)
        fitness_class = class_res.scalar_one_or_none()
        if not fitness_class:
            raise HTTPException(status_code=404, detail="Class not found")

        # Double check active bookings
        dup_query = select(Reservation).where(
            Reservation.class_id == class_id,
            Reservation.user_id == user_id,
            Reservation.status.in_(["CONFIRMED", "WAITLISTED"])
        )
        dup_res = await db.execute(dup_query)
        if dup_res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Duplicate registration entry detected")

        # Process deduction first
        pack_id = await LedgerService.consume_credit_atomic(db, user_id)

        if fitness_class.available_spots > 0:
            fitness_class.available_spots -= 1
            res_status = "CONFIRMED"
            msg = "Spot confirmed successfully."
        else:
            res_status = "WAITLISTED"
            msg = "Class full. Assigned to waitlist queue."

        reservation = Reservation(
            class_id=class_id,
            user_id=user_id,
            status=res_status
        )
        db.add(reservation)
        await db.flush()
        return reservation, msg

    @staticmethod
    async def cancel_booking(db: AsyncSession, user_id: uuid.UUID, reservation_id: uuid.UUID) -> Dict[str, str]:
        res_query = select(Reservation).where(Reservation.id == reservation_id).with_for_update()
        res_exec = await db.execute(res_query)
        reservation = res_exec.scalar_one_or_none()
        if not reservation or reservation.status in ["CANCELLED", "WAITLIST_LEFT"]:
            raise HTTPException(status_code=404, detail="Active reservation context missing")

        if reservation.user_id != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized action context mapping")

        class_query = select(FitnessClass).where(FitnessClass.id == reservation.class_id).with_for_update()
        class_exec = await db.execute(class_query)
        fitness_class = class_exec.scalar_one_or_none()

        studio = await db.get(Studio, fitness_class.studio_id)

        now = datetime.utcnow()
        time_diff_hours = (fitness_class.start_time - now).total_seconds() / 3600
        is_late_cancel = time_diff_hours < studio.cancellation_cutoff_hours

        was_confirmed = reservation.status == "CONFIRMED"

        if reservation.status == "WAITLISTED":
            reservation.status = "WAITLIST_LEFT"
            # Return credit unconditionally for waitlist drop
            orig_booking = select(CreditLedger).where(
                CreditLedger.user_id == user_id,
                CreditLedger.action_type == "BOOKING"
            ).order_by(CreditLedger.created_at.desc()).limit(1)
            ob_res = await db.execute(orig_booking)
            last_entry = ob_res.scalar_one_or_none()
            pack_id = last_entry.credit_pack_id if last_entry else None

            refund = CreditLedger(user_id=user_id, credit_pack_id=pack_id, amount=1, action_type="CANCEL_REFUND",
                                  created_at=now)
            db.add(refund)
            return {"status": "success", "message": "Left waitlist. Credits returned."}

        reservation.status = "CANCELLED"

        if was_confirmed:
            # Find the linked credit pack usage to refund to the identical tracking account
            orig_booking = select(CreditLedger).where(
                CreditLedger.user_id == user_id,
                CreditLedger.action_type == "BOOKING"
            ).order_by(CreditLedger.created_at.desc()).limit(1)
            ob_res = await db.execute(orig_booking)
            last_entry = ob_res.scalar_one_or_none()
            pack_id = last_entry.credit_pack_id if last_entry else None

            if not is_late_cancel:
                refund = CreditLedger(user_id=user_id, credit_pack_id=pack_id, amount=1, action_type="CANCEL_REFUND",
                                      created_at=now)
                db.add(refund)
                fitness_class.available_spots += 1
                await BookingService._promote_waitlist(db, fitness_class.id)
                return {"status": "success", "message": "Early cancellation processed. Credit returned."}
            else:
                fitness_class.available_spots += 1
                await BookingService._promote_waitlist(db, fitness_class.id)
                return {"status": "success", "message": "Late cancellation processed. Credit forfeited."}

        return {"status": "success", "message": "Operation completed."}

    @staticmethod
    async def _promote_waitlist(db: AsyncSession, class_id: uuid.UUID) -> None:
        wl_query = select(Reservation).where(
            Reservation.class_id == class_id,
            Reservation.status == "WAITLISTED"
        ).order_by(Reservation.created_at.asc()).with_for_update().limit(1)

        wl_res = await db.execute(wl_query)
        next_res = wl_res.scalar_one_or_none()

        if next_res:
            class_query = select(FitnessClass).where(FitnessClass.id == class_id).with_for_update()
            c_exec = await db.execute(class_query)
            fitness_class = c_exec.scalar_one()

            if fitness_class.available_spots > 0:
                fitness_class.available_spots -= 1
                next_res.status = "CONFIRMED"
