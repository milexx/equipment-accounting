from dataclasses import dataclass, field

from app.models.enums import EquipmentCondition, EquipmentStatus


@dataclass(frozen=True)
class EquipmentCreateData:
    region_id: int
    equipment_type_id: int
    title: str
    location: str
    condition: EquipmentCondition
    status: EquipmentStatus
    inventory_number: str | None = None
    serial_number: str | None = None
    comment: str | None = None
    defect_description: str | None = None
    completeness: str | None = None
    attributes: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EquipmentUpdateData:
    title: str
    location: str
    condition: EquipmentCondition
    row_version: int
    submit_after_save: bool = False
    inventory_number: str | None = None
    serial_number: str | None = None
    comment: str | None = None
    defect_description: str | None = None
    completeness: str | None = None
    attributes: dict = field(default_factory=dict)
