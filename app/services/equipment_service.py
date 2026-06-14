from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import EquipmentAuditLog
from app.models.equipment import Equipment
from app.models.enums import (
    EquipmentCondition,
    EquipmentDisposition,
    EquipmentFieldType,
    EquipmentSaleStatus,
    EquipmentStatus,
)
from app.repositories.audit_repository import AuditRepository
from app.repositories.equipment_repository import (
    EquipmentFilters,
    EquipmentListResult,
    EquipmentRepository,
)
from app.repositories.equipment_type_repository import EquipmentTypeRepository
from app.repositories.region_repository import RegionRepository
from app.schemas.equipment import EquipmentCreateData, EquipmentUpdateData


class EquipmentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = EquipmentRepository(db)
        self.audit_repository = AuditRepository(db)
        self.type_repository = EquipmentTypeRepository(db)
        self.region_repository = RegionRepository(db)

    def list_equipment(
        self,
        *,
        region_id: int | None = None,
        equipment_type_id: int | None = None,
        status: EquipmentStatus | None = None,
        condition: EquipmentCondition | None = None,
        disposition: EquipmentDisposition | None = None,
        sale_status: EquipmentSaleStatus | None = None,
        queue: str | None = None,
        query: str | None = None,
        location: str | None = None,
        attribute_filters: dict[str, str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> EquipmentListResult:
        return self.repository.list(
            EquipmentFilters(
                status=status,
                region_id=region_id,
                equipment_type_id=equipment_type_id,
                condition=condition,
                disposition=disposition,
                sale_status=sale_status,
                queue=queue,
                query=query,
                location=location,
                attribute_filters=attribute_filters,
                page=page,
                page_size=page_size,
            )
        )

    def export_equipment(
        self,
        *,
        region_id: int | None = None,
        equipment_type_id: int | None = None,
        status: EquipmentStatus | None = None,
        condition: EquipmentCondition | None = None,
        disposition: EquipmentDisposition | None = None,
        sale_status: EquipmentSaleStatus | None = None,
        queue: str | None = None,
        query: str | None = None,
        location: str | None = None,
        attribute_filters: dict[str, str] | None = None,
        limit: int = 10_000,
    ) -> list[Equipment]:
        return self.repository.export(
            EquipmentFilters(
                region_id=region_id,
                equipment_type_id=equipment_type_id,
                status=status,
                condition=condition,
                disposition=disposition,
                sale_status=sale_status,
                queue=queue,
                query=query,
                location=location,
                attribute_filters=attribute_filters,
                page=1,
                page_size=limit,
            ),
            limit=limit,
        )

    def queue_counts(self) -> dict[str, int]:
        return self.repository.queue_counts()

    def region_status_counts(self, region_id: int) -> dict[str, int]:
        return self.repository.region_status_counts(region_id)

    def get_equipment(self, equipment_id: int):
        return self.repository.get(equipment_id)

    def list_audit_log(self, equipment_id: int) -> list[EquipmentAuditLog]:
        return self.audit_repository.list_for_equipment(equipment_id)

    def apply_center_action(
        self,
        *,
        equipment_id: int,
        action: str,
        expected_row_version: int,
        comment: str | None = None,
    ) -> Equipment:
        stmt = (
            select(Equipment)
            .where(Equipment.id == equipment_id, Equipment.deleted_at.is_(None))
            .with_for_update()
        )
        equipment = self.db.scalar(stmt)
        if equipment is None:
            raise ValueError("Карточка не найдена.")
        if equipment.row_version != expected_row_version:
            raise ValueError("Карточку уже изменили. Обновите страницу и повторите действие.")

        old_data = self._audit_snapshot(equipment)
        self._apply_transition(equipment, action, comment)
        equipment.row_version += 1
        equipment.updated_at = func.now()

        self.audit_repository.add(
            EquipmentAuditLog(
                equipment_id=equipment.id,
                action=f"center.{action}",
                old_data=old_data,
                new_data=self._audit_snapshot(equipment) | {"comment": (comment or "").strip()},
            )
        )
        self.db.commit()
        self.db.refresh(equipment)
        return equipment

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

        title = data.title.strip()
        location = data.location.strip()
        inventory_number = (data.inventory_number or "").strip() or None
        serial_number = (data.serial_number or "").strip() or None

        duplicate = self.repository.find_recent_duplicate(
            region_id=data.region_id,
            equipment_type_id=data.equipment_type_id,
            title=title,
            location=location,
            inventory_number=inventory_number,
            serial_number=serial_number,
            created_within=timedelta(minutes=5),
        )
        if duplicate:
            return duplicate

        attributes = self._validate_attributes(equipment_type.fields, data.attributes, data.status)

        equipment = Equipment(
            region_id=data.region_id,
            equipment_type_id=data.equipment_type_id,
            status=data.status,
            title=title,
            inventory_number=inventory_number,
            serial_number=serial_number,
            location=location,
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

    def update_equipment(self, equipment_id: int, data: EquipmentUpdateData) -> Equipment:
        stmt = (
            select(Equipment)
            .where(Equipment.id == equipment_id, Equipment.deleted_at.is_(None))
            .with_for_update()
        )
        equipment = self.db.scalar(stmt)
        if equipment is None:
            raise ValueError("Карточка не найдена.")
        if equipment.row_version != data.row_version:
            raise ValueError("Карточку уже изменили. Обновите страницу и повторите сохранение.")

        if equipment.status == EquipmentStatus.deleted:
            raise ValueError("Удалённую карточку нельзя редактировать.")
        if not data.title.strip():
            raise ValueError("Заполните наименование.")
        if not data.location.strip():
            raise ValueError("Заполните местонахождение.")
        if data.condition == EquipmentCondition.broken and not (data.defect_description or "").strip():
            raise ValueError("Для нерабочего оборудования опишите поломку.")

        equipment_type = self.type_repository.get_active(equipment.equipment_type_id)
        if equipment_type is None:
            raise ValueError("Тип оборудования не найден или отключён.")

        old_data = self._audit_snapshot(equipment) | self._audit_edit_snapshot(equipment)
        equipment.title = data.title.strip()
        equipment.location = data.location.strip()
        equipment.inventory_number = (data.inventory_number or "").strip() or None
        equipment.serial_number = (data.serial_number or "").strip() or None
        equipment.completeness = (data.completeness or "").strip() or None
        equipment.defect_description = (data.defect_description or "").strip() or None
        equipment.comment = (data.comment or "").strip() or None
        equipment.condition = data.condition
        equipment.attributes = self._validate_attributes(
            equipment_type.fields,
            data.attributes,
            equipment.status,
        )
        if data.submit_after_save:
            if equipment.status not in {EquipmentStatus.draft, EquipmentStatus.needs_revision}:
                raise ValueError("Отправить в центр можно только черновик или запись на доработке.")
            equipment.status = EquipmentStatus.submitted
            equipment.revision_comment = None
        elif equipment.status == EquipmentStatus.needs_revision:
            equipment.status = EquipmentStatus.draft
            equipment.revision_comment = None
        equipment.row_version += 1
        equipment.updated_at = func.now()

        self.audit_repository.add(
            EquipmentAuditLog(
                equipment_id=equipment.id,
                action="equipment.update",
                old_data=old_data,
                new_data=self._audit_snapshot(equipment) | self._audit_edit_snapshot(equipment),
            )
        )
        self.db.commit()
        self.db.refresh(equipment)
        return equipment

    def _apply_transition(self, equipment: Equipment, action: str, comment: str | None) -> None:
        if equipment.status == EquipmentStatus.deleted:
            raise ValueError("Удалённую карточку нельзя изменить.")

        if action == "accept":
            if equipment.status not in {EquipmentStatus.submitted, EquipmentStatus.needs_revision}:
                raise ValueError("Принять можно только запись на проверке или после доработки.")
            equipment.status = EquipmentStatus.accepted
            return

        if action == "revision":
            revision_comment = (comment or "").strip()
            if not revision_comment:
                raise ValueError("Для возврата на доработку нужен комментарий центра.")
            if equipment.status not in {
                EquipmentStatus.submitted,
                EquipmentStatus.accepted,
                EquipmentStatus.diagnostics_required,
            }:
                raise ValueError("Эту запись сейчас нельзя вернуть на доработку.")
            equipment.status = EquipmentStatus.needs_revision
            equipment.revision_comment = revision_comment
            return

        if action == "diagnostics":
            if equipment.status not in {EquipmentStatus.submitted, EquipmentStatus.accepted}:
                raise ValueError("На диагностику можно отправить запись на проверке или принятую запись.")
            equipment.status = EquipmentStatus.diagnostics_required
            equipment.condition = EquipmentCondition.requires_diagnostics
            return

        if action == "writeoff":
            if equipment.status not in {EquipmentStatus.submitted, EquipmentStatus.accepted}:
                raise ValueError("На списание можно направить запись на проверке или принятую запись.")
            if equipment.condition != EquipmentCondition.broken:
                raise ValueError("На списание направляется только нерабочее оборудование.")
            equipment.status = EquipmentStatus.writeoff_review
            equipment.disposition = EquipmentDisposition.writeoff
            return

        if action == "valuation":
            if equipment.status not in {EquipmentStatus.submitted, EquipmentStatus.accepted}:
                raise ValueError("На оценку можно направить запись на проверке или принятую запись.")
            if equipment.condition == EquipmentCondition.broken:
                raise ValueError("Нерабочее оборудование должно идти на списание, а не на оценку.")
            equipment.status = EquipmentStatus.valuation_pending
            equipment.disposition = EquipmentDisposition.valuation
            return

        if action == "sale":
            if equipment.status not in {EquipmentStatus.valuation_pending, EquipmentStatus.valued}:
                raise ValueError("К продаже можно готовить оборудование после направления на оценку.")
            if equipment.condition == EquipmentCondition.broken:
                raise ValueError("Нерабочее оборудование нельзя направить к продаже.")
            equipment.status = EquipmentStatus.sale_ready
            equipment.disposition = EquipmentDisposition.sale
            return

        raise ValueError("Неизвестное действие центра.")

    def _audit_snapshot(self, equipment: Equipment) -> dict:
        return {
            "status": equipment.status.value,
            "condition": equipment.condition.value,
            "disposition": equipment.disposition.value,
            "sale_status": equipment.sale_status.value,
            "revision_comment": equipment.revision_comment,
            "row_version": equipment.row_version,
        }

    def _audit_edit_snapshot(self, equipment: Equipment) -> dict:
        return {
            "title": equipment.title,
            "location": equipment.location,
            "inventory_number": equipment.inventory_number,
            "serial_number": equipment.serial_number,
            "completeness": equipment.completeness,
            "defect_description": equipment.defect_description,
            "comment": equipment.comment,
            "attributes": equipment.attributes,
        }

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
