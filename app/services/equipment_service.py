from sqlalchemy.orm import Session

from app.models.enums import EquipmentCondition, EquipmentDisposition, EquipmentStatus
from app.repositories.equipment_repository import (
    EquipmentFilters,
    EquipmentListResult,
    EquipmentRepository,
)


class EquipmentService:
    def __init__(self, db: Session) -> None:
        self.repository = EquipmentRepository(db)

    def list_equipment(
        self,
        *,
        status: EquipmentStatus | None = None,
        condition: EquipmentCondition | None = None,
        disposition: EquipmentDisposition | None = None,
        query: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> EquipmentListResult:
        return self.repository.list(
            EquipmentFilters(
                status=status,
                condition=condition,
                disposition=disposition,
                query=query,
                page=page,
                page_size=page_size,
            )
        )

    def get_equipment(self, equipment_id: int):
        return self.repository.get(equipment_id)
