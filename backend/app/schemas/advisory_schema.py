from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class AdvisoryItem(BaseModel):
    """
    Single advisory row (paginated). Field sources:
    - **item (ITEM)**: REGISTRATION (Aircraft Statutory Certificates) | certificate name (Organizational Approvals) | Item Type name (OEM Technical Publication) | NAME (Personnel Authorization).
    - **type (TYPE)**: REGULATORY_CORRESPONDENCE_NON_CERT if Certificate Type MARKING RESERVATION EXPIRY or BINARY CODE 24BIT else CERTIFICATE (Aircraft); CERTIFICATE (Organizational Approvals); category_type (OEM), SUBSCRIPTION; CAAP LIC EXPIRY → LICENSE else CERTIFICATE (Personnel Authorization).
    - **expiry**: date_of_expiration.
    - **remaining_validity**: (today - date_of_expiration).days; negative = days left, positive = overdue.
    """

    item: str = Field(
        ...,
        description="ITEM: from REGISTRATION (Aircraft Statutory Certificates), certificate name (Organizational Approvals), Item Type name (OEM Technical Publication), or NAME (Personnel Authorization)",
    )
    type: str = Field(
        ...,
        description="TYPE: REGULATORY_CORRESPONDENCE_NON_CERT if MARKING RESERVATION/BINARY CODE 24BIT else CERTIFICATE (Aircraft); CERTIFICATE (Org Approvals); category_type/SUBSCRIPTION (OEM); LICENSE for CAAP LIC EXPIRY else CERTIFICATE (Personnel)",
    )
    expiry: Optional[date] = Field(None, description="EXPIRY: date_of_expiration")
    remaining_validity: Optional[int] = Field(
        None,
        description="REMAINING VALIDITY: (today - date_of_expiration).days; negative = days left, positive = overdue",
    )

    class Config:
        orm_mode = False


class AdvisoryExpiryEntry(BaseModel):
    """Expiry and remaining validity for one advisory entry (used when grouped by item and type)."""

    expiry: Optional[date] = Field(None, description="date_of_expiration")
    remaining_validity: Optional[int] = Field(
        None,
        description="(today - date_of_expiration).days; negative = days left, positive = overdue",
    )


class AdvisoryExpiryEntryWithItem(BaseModel):
    """Item plus expiry and remaining validity (used when grouped by type)."""

    item: str = Field(..., description="Item: registration, certificate name, item type name, or person name")
    expiry: Optional[date] = Field(None, description="date_of_expiration")
    remaining_validity: Optional[int] = Field(
        None,
        description="(today - date_of_expiration).days; negative = days left, positive = overdue",
    )


class AdvisoryTypeGroup(BaseModel):
    """Advisory entries grouped by type only, with item and expiry per entry."""

    type: str = Field(
        ...,
        description="Type: CERTIFICATE, REGULATORY_CORRESPONDENCE_NON_CERT, SUBSCRIPTION, or LICENSE",
    )
    entries: list[AdvisoryExpiryEntryWithItem] = Field(
        default_factory=list,
        description="All (item, expiry, remaining_validity) for this type",
    )


class AdvisoryItemGroup(BaseModel):
    """Advisory entries grouped by item and type, with all expiries listed."""

    item: str = Field(..., description="Item: registration, certificate name, item type name, or person name")
    type: str = Field(
        ...,
        description="Type: CERTIFICATE, REGULATORY_CORRESPONDENCE_NON_CERT, SUBSCRIPTION, or LICENSE",
    )
    expiries: list[AdvisoryExpiryEntry] = Field(
        default_factory=list,
        description="All expiry dates and remaining validity for this (item, type)",
    )


class AdvisoryPagedResponse(BaseModel):
    """Paginated advisory list: items (ITEM, TYPE, EXPIRY, REMAINING VALIDITY), total count, page, pages."""

    items: list[AdvisoryItem]
    total: int = Field(..., description="Total number of advisory items")
    page: int = Field(..., description="Current page number (1-based)")
    pages: int = Field(..., description="Total number of pages")

    class Config:
        orm_mode = False


class AdvisoryGroupedPagedResponse(BaseModel):
    """Paged list of advisory groups by item and type, with expiries annotated per group."""

    groups: list[AdvisoryItemGroup]
    total: int
    page: int
    pages: int

    class Config:
        orm_mode = False


class AdvisoryGroupedByTypePagedResponse(BaseModel):
    """Paged list of advisory groups by type, with item and expiry per entry."""

    type_groups: list[AdvisoryTypeGroup]
    total: int
    page: int
    pages: int

    class Config:
        orm_mode = False


class AdvisoryFilterOption(BaseModel):
    """One filter option for the advisory type dropdown (value + label)."""

    value: str = Field(..., description="Value to send as query param ?type=...")
    label: str = Field(..., description="Display label for the filter option")


class AdvisoryFilterOptionsResponse(BaseModel):
    """Filter options for advisory type (for dropdowns)."""

    filters: list[AdvisoryFilterOption] = Field(
        default_factory=list,
        description="List of type filter options (value, label)",
    )
