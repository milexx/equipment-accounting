from sqlalchemy.orm import Session

from app.models.photo import EquipmentPhoto


class EquipmentPhotoRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_all(self, photos: list[EquipmentPhoto]) -> None:
        self.db.add_all(photos)
        self.db.flush()
