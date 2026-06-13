from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import EquipmentAuditLog


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_equipment(self, equipment_id: int, limit: int = 20) -> list[EquipmentAuditLog]:
        stmt = (
            select(EquipmentAuditLog)
            .where(EquipmentAuditLog.equipment_id == equipment_id)
            .order_by(EquipmentAuditLog.created_at.desc(), EquipmentAuditLog.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def add(self, log: EquipmentAuditLog) -> EquipmentAuditLog:
        self.db.add(log)
        self.db.flush()
        return log
