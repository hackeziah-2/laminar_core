from sqlalchemy import Boolean, Column, Integer, Date, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base, TimestampMixin, SoftDeleteMixin


class PersonnelAuthorization(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "personnel_authorization"

    id = Column(Integer, primary_key=True, index=True)
    account_information_id = Column(
        Integer,
        ForeignKey("account_information.id"),
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

    auth_initial_doi = Column(Date, nullable=True)
    auth_issue_date = Column(Date, nullable=True)
    auth_expiry_date = Column(Date, nullable=True)
    caap_license_expiry = Column(Date, nullable=True)
    human_factors_training_expiry = Column(Date, nullable=True)
    type_training_expiry_cessna = Column(Date, nullable=True)
    type_training_expiry_baron = Column(Date, nullable=True)
    is_withhold = Column(Boolean, default=False, nullable=False)

    account_information = relationship(
        "AccountInformation",
        back_populates="personnel_authorizations",
    )
    authorization_scope_cessna = relationship(
        "AuthorizationScopeCessna",
        back_populates="personnel_authorizations",
    )
    authorization_scope_baron = relationship(
        "AuthorizationScopeBaron",
        back_populates="personnel_authorizations",
    )
    authorization_scope_others = relationship(
        "AuthorizationScopeOthers",
        back_populates="personnel_authorizations",
    )

    def __repr__(self):
        return f"<PersonnelAuthorization(id={self.id}, account_information_id={self.account_information_id})>"
