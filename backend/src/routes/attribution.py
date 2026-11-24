from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.middlewares.auth import current_user, require_roles
from src.models import AttributionCorrection, User
from src.schemas.attribution import CorrectionIn, CorrectionReviewIn
from src.services.attribution import correction_summary, review_correction, submit_correction


router = APIRouter(prefix='/attribution-corrections')


@router.get('')
def list_corrections(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(select(AttributionCorrection).order_by(AttributionCorrection.id.desc()))
    return [correction_summary(db, row) for row in rows]


@router.post('', status_code=201)
def submit(payload: CorrectionIn, db: Session = Depends(get_db),
           user: User = Depends(require_roles('analyst'))):
    correction = submit_correction(db, payload, user)
    db.commit()
    return correction_summary(db, correction)


@router.post('/{correction_id}/review')
def review(correction_id: int, payload: CorrectionReviewIn, db: Session = Depends(get_db),
           user: User = Depends(require_roles('admin'))):
    correction = review_correction(db, correction_id, payload, user)
    db.commit()
    return correction_summary(db, correction)
