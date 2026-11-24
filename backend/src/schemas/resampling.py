from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

WindowLabel = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)
]
PositiveId = Annotated[int, Field(gt=0)]
ClaimNote = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]
WINDOW_CHOICES = ('早市', '午市', '下午', '晚市')


class QuotaIn(BaseModel):
    quota_date: date | None = None
    total: int = Field(ge=0, le=999)


class ClaimIn(BaseModel):
    stall_id: PositiveId
    claim_date: date | None = None
    window_label: WindowLabel
    note: ClaimNote = ''


class ClaimCancelIn(BaseModel):
    note: ClaimNote = ''


class SampleClaimRef(BaseModel):
    claim_id: PositiveId | None = None
    submission_key: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None = None
