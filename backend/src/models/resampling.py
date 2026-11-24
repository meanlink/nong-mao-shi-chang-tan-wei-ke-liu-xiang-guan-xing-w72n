from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.config.database import Base


class ResamplingQuota(Base):
    """Daily shared quota configured by the administrator for re-sampling claims."""

    __tablename__ = 'resampling_quotas'

    id: Mapped[int] = mapped_column(primary_key=True)
    quota_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    total: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=func.now())


class ResamplingClaim(Base):
    """One pending/reconciled re-sampling order for a stall and time window on a given day."""

    __tablename__ = 'resampling_claims'
    __table_args__ = (
        Index('ix_resampling_claims_slot', 'stall_id', 'claim_date', 'window_label'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stall_id: Mapped[int] = mapped_column(ForeignKey('stalls.id'), index=True)
    claim_date: Mapped[date] = mapped_column(Date, index=True)
    window_label: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default='pending', index=True)
    note: Mapped[str] = mapped_column(String(255), default='')
    claimed_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    claimed_by_name: Mapped[str] = mapped_column(String(80), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    sample_id: Mapped[int | None] = mapped_column(ForeignKey('footfall_samples.id'), unique=True)
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Storage-only slot marker (MySQL generated column / SQLite expression index).
    # It is 1 for live orders (pending/fulfilled) and NULL once cancelled.
    live_slot_marker: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ResamplingQuotaSlot(Base):
    """One seat of the daily shared quota. A claim atomically takes a free seat
    (claim_id NULL); once every seat is taken the day is full, so the table enforces
    the cap even when row locks are unavailable."""

    __tablename__ = 'resampling_quota_slots'
    __table_args__ = (
        Index('uq_resampling_quota_slots_day_no', 'quota_date', 'slot_no', unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    quota_date: Mapped[date] = mapped_column(Date, index=True)
    slot_no: Mapped[int] = mapped_column(Integer)
    claim_id: Mapped[int | None] = mapped_column(Integer, unique=True)
