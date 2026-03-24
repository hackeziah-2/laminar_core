from datetime import date
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

RegulatoryComplianceSource = Literal[
    "aircraft-statutory-certificates",
    "organizational-approvals",
    "oem-technical-publication",
    "personnel-compliance",
]


class AdvisoryItem(BaseModel):
    id: Optional[int] = Field(None, description="ID of the source record")
    regulatory_compliance: RegulatoryComplianceSource = Field(
        ...,
        description="Source of the advisory: aircraft-statutory-certificates, organizational-approvals, oem-technical-publication, or personnel-compliance",
    )
    ITEM: str = Field(..., description="Source item name")
    TYPE: str = Field(..., description="Advisory type")
    EXPIRY: Optional[date] = Field(None, description="Expiry date")
    REMAINING_VALIDITY: Optional[int] = Field(
        None,
        description="expiry_date - today (personnel compliance: expiry_date; else date_of_expiration). Positive = days left, <= 0 = expired.",
    )
    REMAINING_DAYS: Optional[Union[str, int]] = Field(
        None,
        description="If REMAINING_VALIDITY <= 0: 'Expired'; elif REMAINING_VALIDITY <= 30: REMAINING_VALIDITY (int).",
    )
    category_type: Optional[str] = Field(
        None,
        description="Source-specific label; for personnel-compliance, PersonnelComplianceItemType value (e.g. CAAP_LICENSE).",
    )

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
        description="Source of the advisory: aircraft-statutory-certificates, organizational-approvals, oem-technical-publication, or personnel-compliance",
    )
    category_type: Optional[str] = Field(
        None,
        description="Optional; ignored. Personnel compliance rows use item_type on the record (not this field).",
    )
