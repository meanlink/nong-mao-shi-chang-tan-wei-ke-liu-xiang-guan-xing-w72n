from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import AttributionCorrection, CampaignWindow, FootfallSample, Stall, User
from src.schemas.attribution import CorrectionIn, CorrectionReviewIn
from src.services.audit import record
from src.services.market import classify_sample


def is_current_sample():
    """Use the replacement in live counts while keeping historical sample IDs readable."""
    return ~select(AttributionCorrection.id).where(
        AttributionCorrection.sample_id == FootfallSample.id,
        AttributionCorrection.replacement_sample_id.is_not(None),
    ).exists()


def campaign_for_sample(db: Session, sample: FootfallSample, campaign_id: int | None):
    if campaign_id is None:
        return None
    campaign = db.get(CampaignWindow, campaign_id)
    if campaign is None:
        raise HTTPException(404, '拟归属的活动不存在')
    stall = db.get(Stall, sample.stall_id)
    if campaign.target_zone not in ('全场', stall.zone):
        raise HTTPException(422, '活动覆盖区域与采样摊位不符')
    if not campaign.starts_at <= sample.sampled_at <= campaign.ends_at:
        raise HTTPException(422, '采样时间不在拟归属的活动窗口内')
    return campaign


def submit_correction(db: Session, payload: CorrectionIn, user: User):
    # A locking read of the source sample serializes submissions for the same observation.
    sample = db.get(FootfallSample, payload.sample_id, with_for_update=True)
    if sample is None:
        raise HTTPException(404, '客流样本不存在')
    if sample.status != 'conflicting':
        raise HTTPException(422, '只有活动归属冲突的样本可以提交更正')
    existing = db.scalar(
        select(AttributionCorrection.id)
        .where(AttributionCorrection.sample_id == sample.id,
               AttributionCorrection.status.in_(('pending', 'approved')))
        .with_for_update()
    )
    if existing is not None:
        raise HTTPException(409, '该样本已有待复核或已批准的更正')
    campaign_for_sample(db, sample, payload.proposed_campaign_id)
    correction = AttributionCorrection(**payload.model_dump(), requested_by=user.id)
    db.add(correction)
    db.flush()
    record(db, user.email, 'attribution.submitted', {
        'id': correction.id, 'sample_id': sample.id,
        'proposed_campaign_id': correction.proposed_campaign_id,
    })
    return correction


def review_correction(db: Session, correction_id: int, payload: CorrectionReviewIn, user: User):
    correction = db.get(AttributionCorrection, correction_id, with_for_update=True)
    if correction is None:
        raise HTTPException(404, '活动归属更正单不存在')
    if correction.status != 'pending':
        raise HTTPException(409, '只有待复核的更正单可以处理')

    if payload.decision == 'approve':
        sample = db.get(FootfallSample, correction.sample_id)
        campaign = campaign_for_sample(db, sample, correction.proposed_campaign_id)
        replacement = FootfallSample(
            stall_id=sample.stall_id, sampled_at=sample.sampled_at,
            window_label=sample.window_label, footfall=sample.footfall,
            transactions=sample.transactions, revenue=sample.revenue,
            dwell_seconds=sample.dwell_seconds, weather=sample.weather,
            source=sample.source, notes=sample.notes,
            campaign_window_id=campaign.id if campaign else None,
            campaign_label=campaign.label if campaign else '',
        )
        classify_sample(db, replacement)
        if replacement.status != 'valid':
            raise HTTPException(422, replacement.issue_reason)
        db.add(replacement)
        db.flush()
        correction.replacement_sample_id = replacement.id
        correction.status = 'approved'
    else:
        correction.status = 'rejected'

    correction.reviewed_by = user.id
    correction.review_note = payload.note
    correction.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    record(db, user.email, f'attribution.{correction.status}', {
        'id': correction.id, 'sample_id': correction.sample_id,
        'replacement_sample_id': correction.replacement_sample_id,
    })
    return correction


def correction_summary(db: Session, correction: AttributionCorrection) -> dict:
    sample = db.get(FootfallSample, correction.sample_id)
    stall = db.get(Stall, sample.stall_id)
    campaign = db.get(CampaignWindow, correction.proposed_campaign_id) if correction.proposed_campaign_id else None
    author = db.get(User, correction.requested_by)
    reviewer = db.get(User, correction.reviewed_by) if correction.reviewed_by else None
    return {
        'id': correction.id,
        'sample_id': sample.id, 'stall_code': stall.code, 'stall_name': stall.name,
        'sampled_at': sample.sampled_at.isoformat(), 'original_label': sample.campaign_label,
        'original_issue': sample.issue_reason,
        'proposed_campaign_id': correction.proposed_campaign_id,
        'proposed_campaign_name': campaign.name if campaign else None,
        'replacement_sample_id': correction.replacement_sample_id,
        'status': correction.status, 'evidence': correction.evidence,
        'requested_by': author.name, 'created_at': correction.created_at.isoformat(),
        'reviewed_by': reviewer.name if reviewer else None, 'review_note': correction.review_note,
        'reviewed_at': correction.reviewed_at.isoformat() if correction.reviewed_at else None,
    }
