from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.region import Region


class RegionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active_regions(self) -> list[Region]:
        stmt = (
            select(Region)
            .where(Region.is_active.is_(True), Region.code != "CENTER")
            .order_by(Region.name)
        )
        return list(self.db.scalars(stmt))

    def get(self, region_id: int) -> Region | None:
        return self.db.get(Region, region_id)

