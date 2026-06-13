from dataclasses import dataclass

from datetime import timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.equipment import Equipment
from app.models.enums import EquipmentCondition, EquipmentDisposition, EquipmentStatus


QUEUE_FILTERS = {
    "review": Equipment.status == EquipmentStatus.submitted,
    "revision": Equipment.status == EquipmentStatus.needs_revision,
    "diagnostics": Equipment.status == EquipmentStatus.diagnostics_required,
    "writeoff": Equipment.status.in_(
        [
            EquipmentStatus.writeoff_review,
            EquipmentStatus.writeoff_approved,
            EquipmentStatus.disposal_pending,
        ]
    ),
    "sale": Equipment.status.in_(
        [
            EquipmentStatus.valuation_pending,
            EquipmentStatus.valued,
            EquipmentStatus.sale_ready,
            EquipmentStatus.listed_for_sale,
        ]
    ),
}


@dataclass(frozen=True)
class EquipmentFilters:
    status: EquipmentStatus | None = None
    condition: EquipmentCondition | None = None
    disposition: EquipmentDisposition | None = None
    queue: str | None = None
    query: str | None = None
    page: int = 1
    page_size: int = 50


@dataclass(frozen=True)
class EquipmentListResult:
    items: list[Equipment]
    total: int
    page: int
    page_size: int


class EquipmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, filters: EquipmentFilters) -> EquipmentListResult:
        stmt = self._base_query(filters)
        count_stmt = select(func.count()).select_from(stmt.subquery())

        page = max(filters.page, 1)
        page_size = min(max(filters.page_size, 1), 500)
        offset = (page - 1) * page_size

        items_stmt = (
            stmt.options(joinedload(Equipment.region), joinedload(Equipment.equipment_type))
            .order_by(Equipment.updated_at.desc(), Equipment.id.desc())
            .limit(page_size)
            .offset(offset)
        )

        total = self.db.scalar(count_stmt) or 0
        items = list(self.db.scalars(items_stmt).unique())
        return EquipmentListResult(items=items, total=total, page=page, page_size=page_size)

    def queue_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {
            "all": self.db.scalar(
                select(func.count())
                .select_from(Equipment)
                .where(Equipment.deleted_at.is_(None))
            )
            or 0
        }
        for queue_code, condition in QUEUE_FILTERS.items():
            stmt = (
                select(func.count())
                .select_from(Equipment)
                .where(Equipment.deleted_at.is_(None), condition)
            )
            counts[queue_code] = self.db.scalar(stmt) or 0
        return counts

    def get(self, equipment_id: int) -> Equipment | None:
        stmt = (
            select(Equipment)
            .where(Equipment.id == equipment_id, Equipment.deleted_at.is_(None))
            .options(
                joinedload(Equipment.region),
                joinedload(Equipment.equipment_type),
                joinedload(Equipment.photos),
            )
        )
        return self.db.scalar(stmt)

    def add(self, equipment: Equipment) -> Equipment:
        self.db.add(equipment)
        self.db.flush()
        return equipment

    def find_recent_duplicate(
        self,
        *,
        region_id: int,
        equipment_type_id: int,
        title: str,
        location: str,
        inventory_number: str | None,
        serial_number: str | None,
        created_within: timedelta,
    ) -> Equipment | None:
        threshold = func.now() - created_within
        stmt = (
            select(Equipment)
            .where(
                Equipment.deleted_at.is_(None),
                Equipment.region_id == region_id,
                Equipment.equipment_type_id == equipment_type_id,
                Equipment.title == title,
                Equipment.location == location,
                Equipment.inventory_number.is_not_distinct_from(inventory_number),
                Equipment.serial_number.is_not_distinct_from(serial_number),
                Equipment.created_at >= threshold,
            )
            .order_by(Equipment.created_at.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def _base_query(self, filters: EquipmentFilters) -> Select[tuple[Equipment]]:
        stmt = select(Equipment).where(Equipment.deleted_at.is_(None))

        if filters.status:
            stmt = stmt.where(Equipment.status == filters.status)
        if filters.condition:
            stmt = stmt.where(Equipment.condition == filters.condition)
        if filters.disposition:
            stmt = stmt.where(Equipment.disposition == filters.disposition)
        if filters.queue in QUEUE_FILTERS:
            stmt = stmt.where(QUEUE_FILTERS[filters.queue])
        if filters.query:
            like = f"%{filters.query.strip()}%"
            stmt = stmt.where(
                Equipment.title.ilike(like)
                | Equipment.inventory_number.ilike(like)
                | Equipment.serial_number.ilike(like)
            )

        return stmt
