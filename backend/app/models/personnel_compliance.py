import enum

from sqlalchemy import Boolean, Column, Integer, Date, ForeignKey
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin, AuditMixin


class PersonnelComplianceItemType(str, enum.Enum):
    AUTH_EXPIRY = "AUTH_EXPIRY"
    CAAP_LICENSE = "CAAP_LICENSE"
    HF_TRAINING = "HF_TRAINING"
    CESSNA = "CESSNA"
    BARON = "BARON"
    OTHERS = "OTHERS"


class PersonnelCompliance(Base, TimestampMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "personnel_compliance"

    id = Column(Integer, primary_key=True, index=True)
    account_information_id = Column(
        Integer,
        ForeignKey("account_information.id"),
        nullable=False,
        index=True,
    )
    item_type = Column(
        PGEnum(
            PersonnelComplianceItemType,
            name="personnel_compliance_item_type",
            create_type=True,
        ),
        nullable=False,
        index=True,
    )
    authorization_scope_cessna_id = Column(
        Integer,
        ForeignKey("authorization_scope_cessna.id"),
        nullable=True,
        index=True,
    )
    authorization_scope_baron_id = Column(
        Integer,
        ForeignKey("authorization_scope_baron.id"),
        nullable=True,
        index=True,
    )
    authorization_scope_others_id = Column(
        Integer,
        ForeignKey("authorization_scope_others.id"),
        nullable=True,
        index=True,
    )
    auth_issue_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    is_withhold = Column(Boolean, default=False, nullable=False)

    account_information = relationship(
        "AccountInformation",
        foreign_keys=[account_information_id],
        back_populates="personnel_compliances",
    )
    authorization_scope_cessna = relationship(
        "AuthorizationScopeCessna",
        back_populates="personnel_compliances",
    )
    authorization_scope_baron = relationship(
        "AuthorizationScopeBaron",
        back_populates="personnel_compliances",
    )
    authorization_scope_others = relationship(
        "AuthorizationScopeOthers",
        back_populates="personnel_compliances",
    )

    def __repr__(self):
        return (
            f"<PersonnelCompliance(id={self.id}, account_information_id="
            f"{self.account_information_id}, item_type={self.item_type})>"
        )
