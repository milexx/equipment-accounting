from sqlalchemy.orm import Session

from app.models.equipment import Equipment
from app.models.enums import (
    EquipmentCondition,
    EquipmentDisposition,
    EquipmentFieldType,
    EquipmentStatus,
)
from app.repositories.equipment_repository import (
    EquipmentFilters,
    EquipmentListResult,
    EquipmentRepository,
)
from app.repositories.equipment_type_repository import EquipmentTypeRepository
from app.repositories.region_repository import RegionRepository
from app.schemas.equipment import EquipmentCreateData


class EquipmentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = EquipmentRepository(db)
        self.type_repository = EquipmentTypeRepository(db)
        self.region_repository = RegionRepository(db)

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

    def create_equipment(self, data: EquipmentCreateData) -> Equipment:
        equipment_type = self.type_repository.get_active(data.equipment_type_id)
        if equipment_type is None:
            raise ValueError("Не выбран тип оборудования.")

        region = self.region_repository.get(data.region_id)
        if region is None or not region.is_active:
            raise ValueError("Не выбран регион.")

        if not data.title.strip():
            raise ValueError("Заполните наименование.")
        if not data.location.strip():
            raise ValueError("Заполните местонахождение.")
        if data.condition == EquipmentCondition.broken and not (data.defect_description or "").strip():
            raise ValueError("Для нерабочего оборудования опишите поломку.")

        attributes = self._validate_attributes(equipment_type.fields, data.attributes, data.status)

        equipment = Equipment(
            region_id=data.region_id,
            equipment_type_id=data.equipment_type_id,
            status=data.status,
            title=data.title.strip(),
            inventory_number=(data.inventory_number or "").strip() or None,
            serial_number=(data.serial_number or "").strip() or None,
            location=data.location.strip(),
            condition=data.condition,
            comment=(data.comment or "").strip() or None,
            defect_description=(data.defect_description or "").strip() or None,
            completeness=(data.completeness or "").strip() or None,
            attributes=attributes,
        )
        self.repository.add(equipment)
        self.db.commit()
        self.db.refresh(equipment)
        return equipment

    def _validate_attributes(self, fields, raw_attributes: dict, status: EquipmentStatus) -> dict:
        attributes = {}
        for field in sorted(fields, key=lambda item: item.display_order):
            if not field.is_active:
                continue
            raw_value = raw_attributes.get(field.code)
            value = self._coerce_attribute(field.field_type, raw_value)
            if status == EquipmentStatus.submitted and field.is_required and value in (None, "", []):
                raise ValueError(f"Заполните поле: {field.name}.")
            if value not in (None, "", []):
                attributes[field.code] = value
        return attributes

    def _coerce_attribute(self, field_type: EquipmentFieldType, raw_value):
        if raw_value is None:
            return None
        if isinstance(raw_value, str):
            raw_value = raw_value.strip()
        if raw_value == "":
            return None
        if field_type == EquipmentFieldType.integer:
            return int(raw_value)
        if field_type == EquipmentFieldType.decimal:
            return float(raw_value)
        if field_type == EquipmentFieldType.boolean:
            return raw_value in ("1", "true", "yes", "on", True)
        return raw_value
