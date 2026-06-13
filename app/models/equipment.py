from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import (
    EquipmentCondition,
    EquipmentDisposition,
    EquipmentSaleStatus,
    EquipmentStatus,
)


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), nullable=False)
    equipment_type_id: Mapped[int] = mapped_column(ForeignKey("equipment_types.id"), nullable=False)
    status: Mapped[EquipmentStatus] = mapped_column(
        Enum(EquipmentStatus, name="equipment_status"), nullable=False, default=EquipmentStatus.draft
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    inventory_number: Mapped[str | None] = mapped_column(Text)
    serial_number: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    condition: Mapped[EquipmentCondition] = mapped_column(
        Enum(EquipmentCondition, name="equipment_condition"),
        nullable=False,
        default=EquipmentCondition.unknown,
    )
    disposition: Mapped[EquipmentDisposition] = mapped_column(
        Enum(EquipmentDisposition, name="equipment_disposition"),
        nullable=False,
        default=EquipmentDisposition.undecided,
    )
    sale_status: Mapped[EquipmentSaleStatus] = mapped_column(
        Enum(EquipmentSaleStatus, name="equipment_sale_status"),
        nullable=False,
        default=EquipmentSaleStatus.not_for_sale,
    )
    comment: Mapped[str | None] = mapped_column(Text)
    revision_comment: Mapped[str | None] = mapped_column(Text)
    defect_description: Mapped[str | None] = mapped_column(Text)
    completeness: Mapped[str | None] = mapped_column(Text)
    valuation_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    sale_description: Mapped[str | None] = mapped_column(Text)
    is_public_listing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    region = relationship("Region", back_populates="equipment_items")
    equipment_type = relationship("EquipmentType", back_populates="equipment_items")
    photos = relationship(
        "EquipmentPhoto",
        back_populates="equipment",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
