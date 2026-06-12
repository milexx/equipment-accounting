from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.equipment_type import EquipmentType


class EquipmentTypeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active(self) -> list[EquipmentType]:
        stmt = (
            select(EquipmentType)
            .where(EquipmentType.is_active.is_(True))
            .options(selectinload(EquipmentType.fields))
            .order_by(EquipmentType.name)
        )
        return list(self.db.scalars(stmt))

    def get_active(self, equipment_type_id: int) -> EquipmentType | None:
        stmt = (
            select(EquipmentType)
            .where(EquipmentType.id == equipment_type_id, EquipmentType.is_active.is_(True))
            .options(selectinload(EquipmentType.fields))
        )
        return self.db.scalar(stmt)

