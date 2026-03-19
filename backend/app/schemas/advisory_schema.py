from datetime import date
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

RegulatoryComplianceSource = Literal[
    "aircraft-statutory-certificates",
    "organizational-approvals",
    "oem-technical-publication",
    "personnel-authorization",
]


class AdvisoryItem(BaseModel):
    id: Optional[int] = Field(None, description="ID of the source record")
    regulatory_compliance: RegulatoryComplianceSource = Field(
        ...,
        description="Source of the advisory: aircraft-statutory-certificates, organizational-approvals, oem-technical-publication, or personnel-authorization",
    )
    ITEM: str = Field(..., description="Source item name")
    TYPE: str = Field(..., description="Advisory type")
    EXPIRY: Optional[date] = Field(None, description="Expiry date")
    REMAINING_VALIDITY: Optional[int] = Field(
        None,
        description="expiry_date - today. From Personnel: auth_expiry_date, human_factors_training_expiry, type_training_expiry_cessna/baron - today; else date_of_expiration - today. Positive = days left, <= 0 = expired.",
    )
    REMAINING_DAYS: Optional[Union[str, int]] = Field(
        None,
        description="If REMAINING_VALIDITY <= 0: 'Expired'; elif REMAINING_VALIDITY <= 30: REMAINING_VALIDITY (int).",
    )
    category_type: Optional[str] = Field(None, description="Category type (e.g. AUTH EXPIRATION, CESSNA TRAINING, or source-specific label)")

    class Config:
        orm_mode = False


class AdvisoryFilterOption(BaseModel):
    value: str = Field(..., description="Filter value")
    label: str = Field(..., description="Filter label")


class AdvisoryPagedResponse(BaseModel):
    items: list[AdvisoryItem] = Field(default_factory=list)
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    pages: int = Field(..., description="Total number of pages")

    class Config:
        orm_mode = False


class AdvisoryFilterOptionsResponse(BaseModel):
    filters: list[AdvisoryFilterOption] = Field(default_factory=list)


class AdvisoryUpdateExpiryBody(BaseModel):
    """Request body for PUT /advisory/{id}/{expiry}/."""

    regulatory_compliance: RegulatoryComplianceSource = Field(
        ...,
        description="Source of the advisory: aircraft-statutory-certificates, organizational-approvals, oem-technical-publication, or personnel-authorization",
    )
    category_type: Optional[str] = Field(
        None,
        description="Required for personnel-authorization: AUTH EXPIRATION, CESSNA TRAINING, CAAP LICENSE, HUMAN FACTORS TRAINING, BARON TRAINING. Ignored for other types.",
    )
