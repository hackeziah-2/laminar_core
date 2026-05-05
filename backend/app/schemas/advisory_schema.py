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
    web_link: str = Field(
        default="",
        max_length=2048,
        description="Source URL when the row has web_link; empty string if unset or personnel-compliance.",
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


class AdvisoryDetailResponse(BaseModel):
    """Response for GET /advisory/{id}/ — source row expiry and link when applicable."""

    expiry_date: Optional[date] = Field(
        None,
        description="Personnel: expiry_date; statutory / approval / OEM: date_of_expiration.",
    )
    web_link: Optional[str] = Field(
        None,
        description="URL on the source record; null for personnel-compliance (no column).",
    )

    class Config:
        orm_mode = False


class AdvisoryUpdateExpiryBody(BaseModel):
    """Request body for PUT /advisory/{id}/{expiry}/ (renewal advisory)."""

    regulatory_compliance: RegulatoryComplianceSource = Field(
        ...,
        description=(
            "Required: source table for this advisory row. Drives the update target and, for "
            "organizational-approvals and aircraft-statutory-certificates, appends a pre-update "
            "snapshot to the matching history table."
        ),
    )
    category_type: Optional[str] = Field(
        None,
        description="Optional; ignored. Personnel compliance rows use item_type on the record (not this field).",
    )
    web_link: Optional[str] = Field(
        default=None,
        max_length=2048,
        description=(
            "Optional URL for statutory / approval / OEM records (ignored for personnel-compliance). "
            "Omit to leave unchanged; send empty string to clear."
        ),
    )
