from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints


EvidenceNote = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=500)]
PositiveId = Annotated[int, Field(gt=0)]


class CorrectionIn(BaseModel):
    sample_id: PositiveId
    # Null explicitly records a non-promotion observation.
    proposed_campaign_id: PositiveId | None
    evidence: EvidenceNote


class CorrectionReviewIn(BaseModel):
    decision: Literal['approve', 'reject']
    note: EvidenceNote
