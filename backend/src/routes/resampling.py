from datetime import date as date_cls

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.middlewares.auth import current_user, require_roles
from src.models import ResamplingClaim, User
from src.schemas.resampling import ClaimCancelIn, ClaimIn, QuotaIn
from src.services.resampling import (
    cancel_claim, claim_summary, create_claim, find_live_claim, quota_snapshot, set_quota,
)

router = APIRouter(prefix='/resampling')


@router.get('/quota')
def quota(quota_date: date_cls | None = None, db: Session = Depends(get_db),
          user: User = Depends(current_user)):
    return quota_snapshot(db, quota_date or date_cls.today())


@router.put('/quota')
def update_quota(payload: QuotaIn, db: Session = Depends(get_db),
                 user: User = Depends(require_roles('admin'))):
    target = payload.quota_date or date_cls.today()
    quota_row = set_quota(db, target, payload.total, user)
    db.commit()
    db.refresh(quota_row)
    return quota_snapshot(db, target)


@router.get('/claims')
def list_claims(quota_date: date_cls | None = None, stall_id: int | None = None,
                db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(ResamplingClaim).order_by(ResamplingClaim.id.desc())
    if quota_date:
        query = query.where(ResamplingClaim.claim_date == quota_date)
    if stall_id:
        query = query.where(ResamplingClaim.stall_id == stall_id)
    return [claim_summary(db, row) for row in db.scalars(query.limit(200))]


@router.post('/claims', status_code=201)
def claim(payload: ClaimIn, db: Session = Depends(get_db),
          user: User = Depends(require_roles('admin', 'analyst'))):
    row = create_claim(db, payload, user)
    db.commit()
    db.refresh(row)
    return claim_summary(db, row)


@router.post('/claims/{claim_id}/cancel')
def cancel(claim_id: int, payload: ClaimCancelIn, db: Session = Depends(get_db),
           user: User = Depends(require_roles('admin', 'analyst'))):
    row = cancel_claim(db, claim_id, user, payload.note)
    db.commit()
    db.refresh(row)
    return claim_summary(db, row)


@router.get('/claims/live')
def live_claim(stall_id: int, window_label: str, quota_date: date_cls | None = None,
               db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = find_live_claim(db, stall_id, quota_date or date_cls.today(), window_label)
    return claim_summary(db, row) if row else None
