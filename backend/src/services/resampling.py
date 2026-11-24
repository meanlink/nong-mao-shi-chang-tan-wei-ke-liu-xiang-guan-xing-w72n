from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models import (
    FootfallSample, ResamplingClaim, ResamplingQuota, ResamplingQuotaSlot, Stall, User,
)
from src.schemas.resampling import WINDOW_CHOICES
from src.services.audit import record

LIVE_STATUSES = ('pending', 'fulfilled')


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _validate_window(window_label: str) -> None:
    if window_label not in WINDOW_CHOICES:
        raise HTTPException(422, '时段只能是 早市 / 午市 / 下午 / 晚市')


def get_or_none_quota(db: Session, quota_date: date) -> ResamplingQuota | None:
    return db.scalar(select(ResamplingQuota).where(ResamplingQuota.quota_date == quota_date))


def live_claim_count(db: Session, quota_date: date) -> int:
    # Occupied seats (claim_id set) are the authoritative in-use count.
    return db.scalar(
        select(func.count())
        .select_from(ResamplingQuotaSlot)
        .where(ResamplingQuotaSlot.quota_date == quota_date,
               ResamplingQuotaSlot.claim_id.is_not(None))
    ) or 0


def _sync_seat_pool(db: Session, quota_date: date, total: int) -> None:
    """Grow (or shrink) the fixed seat pool so it matches the configured quota.

    Shrinking only removes still-free seats; occupied seats are never deleted.
    """
    existing = db.scalar(
        select(func.count()).select_from(ResamplingQuotaSlot)
        .where(ResamplingQuotaSlot.quota_date == quota_date)
    ) or 0
    if total > existing:
        db.add_all([
            ResamplingQuotaSlot(quota_date=quota_date, slot_no=no, claim_id=None)
            for no in range(existing + 1, total + 1)
        ])
    elif total < existing:
        free_ids = db.scalars(
            select(ResamplingQuotaSlot.id)
            .where(ResamplingQuotaSlot.quota_date == quota_date,
                   ResamplingQuotaSlot.claim_id.is_(None))
            .order_by(ResamplingQuotaSlot.slot_no.desc())
            .limit(existing - total)
        ).all()
        if free_ids:
            db.query(ResamplingQuotaSlot).filter(
                ResamplingQuotaSlot.id.in_(free_ids)).delete(synchronize_session=False)
    db.flush()


def quota_snapshot(db: Session, quota_date: date) -> dict:
    quota = get_or_none_quota(db, quota_date)
    total = quota.total if quota else 0
    used = live_claim_count(db, quota_date)
    return {
        'quota_date': quota_date.isoformat(),
        'total': total,
        'used': used,
        'remaining': max(0, total - used),
        'configured': quota is not None,
        'updated_at': quota.updated_at.isoformat() if quota and quota.updated_at
        else (quota.created_at.isoformat() if quota else None),
    }


def set_quota(db: Session, quota_date: date, total: int, user: User) -> ResamplingQuota:
    quota = get_or_none_quota(db, quota_date)
    current_used = live_claim_count(db, quota_date)
    if total < current_used:
        raise HTTPException(422, f'当日已有 {current_used} 张有效认领单，名额不能低于该数量')
    if quota is None:
        quota = ResamplingQuota(quota_date=quota_date, total=total, created_by=user.id)
        db.add(quota)
        db.flush()
    else:
        quota.total = total
    _sync_seat_pool(db, quota_date, total)
    record(db, user.email, 'resampling.quota_set',
           {'quota_date': quota_date.isoformat(), 'total': total})
    return quota


def find_live_claim(db: Session, stall_id: int, claim_date: date,
                    window_label: str, for_update: bool = False) -> ResamplingClaim | None:
    query = (
        select(ResamplingClaim)
        .where(ResamplingClaim.stall_id == stall_id,
               ResamplingClaim.claim_date == claim_date,
               ResamplingClaim.window_label == window_label,
               ResamplingClaim.status.in_(LIVE_STATUSES))
    )
    if for_update:
        query = query.with_for_update()
    return db.scalar(query)


def _take_free_seat(db: Session, quota_date: date, claim_id: int) -> bool:
    """Atomically occupy one free seat. Returns False when the day is fully booked."""
    # Pick a free seat id first, then claim it conditionally; LIMIT 1 works on both
    # MySQL and SQLite, and the WHERE claim_id IS NULL makes double-take impossible.
    free_id = db.scalar(
        select(ResamplingQuotaSlot.id)
        .where(ResamplingQuotaSlot.quota_date == quota_date,
               ResamplingQuotaSlot.claim_id.is_(None))
        .order_by(ResamplingQuotaSlot.slot_no)
        .limit(1)
    )
    if free_id is None:
        return False
    result = db.execute(
        update(ResamplingQuotaSlot)
        .where(ResamplingQuotaSlot.id == free_id,
               ResamplingQuotaSlot.claim_id.is_(None))
        .values(claim_id=claim_id)
    )
    db.flush()
    return result.rowcount == 1


def create_claim(db: Session, payload, user: User) -> ResamplingClaim:
    _validate_window(payload.window_label)
    claim_date = payload.claim_date or date.today()
    stall = db.get(Stall, payload.stall_id)
    if stall is None:
        raise HTTPException(404, '摊位不存在')

    quota = get_or_none_quota(db, claim_date)
    if quota is None:
        raise HTTPException(422, '管理员尚未设定当日补采名额')

    existing = find_live_claim(db, stall.id, claim_date, payload.window_label, for_update=True)
    if existing is not None:
        raise HTTPException(409, '该摊位时段已有一张待补单，不能重复认领')

    if live_claim_count(db, claim_date) >= quota.total:
        raise HTTPException(409, '当日补采名额已用完，无法继续认领')

    claim = ResamplingClaim(
        stall_id=stall.id, claim_date=claim_date, window_label=payload.window_label,
        note=payload.note or '', claimed_by=user.id, claimed_by_name=user.name,
        status='pending',
    )
    db.add(claim)
    try:
        db.flush()
        if not _take_free_seat(db, claim_date, claim.id):
            db.delete(claim)
            db.flush()
            raise HTTPException(409, '当日补采名额已用完，无法继续认领')
    except IntegrityError:
        # Storage-level backstop: a concurrent transaction won the same slot/seat.
        db.rollback()
        raise HTTPException(409, '该摊位时段已被认领或当日名额已用完，请刷新后重试')
    record(db, user.email, 'resampling.claimed', {
        'id': claim.id, 'stall_id': stall.id, 'claim_date': claim_date.isoformat(),
        'window_label': payload.window_label,
    })
    return claim


def cancel_claim(db: Session, claim_id: int, user: User, note: str = '') -> ResamplingClaim:
    claim = db.get(ResamplingClaim, claim_id, with_for_update=True)
    if claim is None:
        raise HTTPException(404, '补采认领单不存在')
    if claim.status == 'cancelled':
        raise HTTPException(409, '认领单已撤销，无需重复操作')
    if claim.status == 'fulfilled':
        raise HTTPException(409, '已核销的认领单不能撤销，名额不予退回')
    # Return the seat: only un-fulfilled orders release quota.
    db.execute(
        update(ResamplingQuotaSlot)
        .where(ResamplingQuotaSlot.claim_id == claim.id)
        .values(claim_id=None)
    )
    claim.status = 'cancelled'
    claim.cancelled_at = _now()
    # The storage-level slot marker flips to NULL automatically and releases the
    # partial unique stall/window slot as well.
    if note:
        claim.note = (claim.note + ' / 撤销：' + note)[:255]
    record(db, user.email, 'resampling.cancelled', {
        'id': claim.id, 'stall_id': claim.stall_id,
        'claim_date': claim.claim_date.isoformat(),
        'window_label': claim.window_label,
    })
    return claim


def attach_sample(db: Session, sample: FootfallSample, claim_id: int | None,
                  submission_key: str | None, user: User) -> FootfallSample | None:
    """Bind a newly created sample to its claim and reconcile when the slot matches.

    Returns the previously stored sample when the same submission is retried, so the
    route can replay it instead of creating / reconciling a second time.
    """
    if not claim_id:
        return None

    if submission_key:
        replay = db.scalar(
            select(FootfallSample).where(FootfallSample.submission_key == submission_key)
        )
        if replay is not None:
            return replay

    claim = db.get(ResamplingClaim, claim_id, with_for_update=True)
    if claim is None:
        raise HTTPException(404, '补采认领单不存在')
    if claim.status == 'cancelled':
        # Late submission after cancellation is archived, never reconciled and never
        # consumes a later order's slot.
        sample.claim_id = None
        sample.notes = (sample.notes + ' / 对应认领单已撤销，样本留档待补').strip()
        record(db, user.email, 'resampling.late_archived', {
            'claim_id': claim.id, 'stall_id': sample.stall_id,
        })
        return None
    if claim.status == 'fulfilled':
        raise HTTPException(409, '该认领单已核销，不能重复补录')

    # Pending claim: stall, date and window must all match before reconciliation.
    if sample.stall_id != claim.stall_id:
        raise HTTPException(422, '样本摊位与认领单不一致，不能核销')
    if sample.sampled_at.date() != claim.claim_date:
        raise HTTPException(422, '样本日期与认领单不一致，不能核销')
    if sample.window_label != claim.window_label:
        raise HTTPException(422, '样本时段与认领单不一致，不能核销')

    sample.claim_id = claim.id
    if submission_key:
        sample.submission_key = submission_key
    db.flush()

    if sample.status == 'valid':
        claim.status = 'fulfilled'
        claim.sample_id = sample.id
        claim.fulfilled_at = _now()
        record(db, user.email, 'resampling.fulfilled', {
            'id': claim.id, 'sample_id': sample.id,
        })
    else:
        # Abnormal observations stay archived for another round; the order stays pending.
        record(db, user.email, 'resampling.abnormal_archived', {
            'id': claim.id, 'sample_id': sample.id,
            'issue_reason': sample.issue_reason,
        })
    return None


def claim_summary(db: Session, claim: ResamplingClaim) -> dict:
    stall = db.get(Stall, claim.stall_id)
    sample = db.get(FootfallSample, claim.sample_id) if claim.sample_id else None
    return {
        'id': claim.id,
        'stall_id': claim.stall_id,
        'stall_code': stall.code if stall else '',
        'stall_name': stall.name if stall else '',
        'claim_date': claim.claim_date.isoformat(),
        'window_label': claim.window_label,
        'status': claim.status,
        'note': claim.note,
        'claimed_by': claim.claimed_by_name,
        'created_at': claim.created_at.isoformat() if claim.created_at else None,
        'sample_id': claim.sample_id,
        'sample_status': sample.status if sample else None,
        'sample_issue_reason': sample.issue_reason if sample else None,
        'fulfilled_at': claim.fulfilled_at.isoformat() if claim.fulfilled_at else None,
        'cancelled_at': claim.cancelled_at.isoformat() if claim.cancelled_at else None,
    }
