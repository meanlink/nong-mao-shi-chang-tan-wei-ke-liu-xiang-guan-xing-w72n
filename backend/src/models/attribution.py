from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base


class AttributionCorrection(Base):
    """Review of the promotion attribution on a preserved footfall observation."""

    __tablename__ = 'attribution_corrections'

    id: Mapped[int] = mapped_column(primary_key=True)
    sample_id: Mapped[int] = mapped_column(ForeignKey('footfall_samples.id'), index=True)
    proposed_campaign_id: Mapped[int | None] = mapped_column(ForeignKey('campaign_windows.id'))
    replacement_sample_id: Mapped[int | None] = mapped_column(
        ForeignKey('footfall_samples.id'), unique=True
    )
    status: Mapped[str] = mapped_column(Enum('pending', 'approved', 'rejected'), default='pending')
    evidence: Mapped[str] = mapped_column(String(500))
    requested_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    review_note: Mapped[str | None] = mapped_column(String(500))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
