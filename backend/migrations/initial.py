from sqlalchemy import inspect, text

from src.config.database import Base, engine
from src.models import (
    AnalysisRun, AttributionCorrection, Brief, CampaignWindow, FootfallSample,
    ResamplingClaim, ResamplingQuota, ResamplingQuotaSlot, Stall, User,
)

# Lightweight column additions for databases created before the resampling feature.
_EXTRA_COLUMNS = {
    'footfall_samples': {
        'claim_id': 'ALTER TABLE footfall_samples ADD COLUMN claim_id INTEGER NULL',
        'submission_key': 'ALTER TABLE footfall_samples ADD COLUMN submission_key VARCHAR(80) NULL',
    },
}
_EXTRA_INDEXES = {
    'footfall_samples': {
        'ix_footfall_samples_claim_id': 'CREATE INDEX ix_footfall_samples_claim_id ON footfall_samples (claim_id)',
        'uq_footfall_samples_submission_key': 'CREATE UNIQUE INDEX uq_footfall_samples_submission_key ON footfall_samples (submission_key)',
    },
}

LIVE_SLOT_INDEX = 'uq_resampling_claims_live_slot'
MARKER_COLUMN = 'live_slot_marker'


def _has_index(inspector, table: str, name: str) -> bool:
    # SQLite cannot reflect expression-based indexes; consult sqlite_master first.
    if engine.dialect.name == 'sqlite':
        with engine.connect() as conn:
            return conn.execute(
                text('SELECT 1 FROM sqlite_master WHERE type = "index" AND name = :n'),
                {'n': name},
            ).first() is not None
    return any(idx['name'] == name for idx in inspector.get_indexes(table))


def _resampling_ddl(conn, inspector):
    if 'resampling_claims' not in set(inspector.get_table_names()):
        return
    dialect = engine.dialect.name
    if dialect == 'sqlite':
        if not _has_index(inspector, 'resampling_claims', LIVE_SLOT_INDEX):
            # Only live (non-cancelled) rows participate; NULLs never conflict.
            conn.execute(text(
                'CREATE UNIQUE INDEX uq_resampling_claims_live_slot '
                'ON resampling_claims ('
                'CASE WHEN status = "cancelled" THEN NULL ELSE 1 END, '
                'stall_id, claim_date, window_label)'
            ))
    else:
        columns = {col['name'] for col in inspector.get_columns('resampling_claims')}
        generated = any(
            col.get('name') == MARKER_COLUMN and col.get('extra')
            for col in inspector.get_columns('resampling_claims')
        )
        if MARKER_COLUMN in columns and not generated:
            # Replace the plain column created by create_all with a generated one.
            conn.execute(text(
                'ALTER TABLE resampling_claims DROP COLUMN live_slot_marker'))
        if MARKER_COLUMN not in columns or not generated:
            conn.execute(text(
                'ALTER TABLE resampling_claims '
                'ADD COLUMN live_slot_marker TINYINT '
                'GENERATED ALWAYS AS (CASE WHEN status = "cancelled" THEN NULL ELSE 1 END) VIRTUAL'))
        if not _has_index(inspector, 'resampling_claims', LIVE_SLOT_INDEX):
            conn.execute(text(
                'CREATE UNIQUE INDEX uq_resampling_claims_live_slot '
                'ON resampling_claims (live_slot_marker, stall_id, claim_date, window_label)'))


def _apply_incremental():
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _EXTRA_COLUMNS.items():
            if table not in tables:
                continue
            existing = {col['name'] for col in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(ddl))
        for table, indexes in _EXTRA_INDEXES.items():
            if table not in tables:
                continue
            existing = {idx['name'] for idx in inspector.get_indexes(table)}
            for name, ddl in indexes.items():
                if name not in existing:
                    conn.execute(text(ddl))
        _resampling_ddl(conn, inspector)


def migrate():
    Base.metadata.create_all(bind=engine)
    _apply_incremental()
