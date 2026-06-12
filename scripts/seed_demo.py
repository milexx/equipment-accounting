from decimal import Decimal

from sqlalchemy import select

import app.models  # noqa: F401
from app.database import SessionLocal
from app.models.equipment import Equipment
from app.models.equipment_type import EquipmentType, EquipmentTypeField
from app.models.enums import (
    EquipmentCondition,
    EquipmentDisposition,
    EquipmentFieldType,
    EquipmentSaleStatus,
    EquipmentStatus,
    UserRole,
)
from app.models.region import Region
from app.models.user import User


def get_or_create_region(db, code: str, name: str) -> Region:
    region = db.scalar(select(Region).where(Region.code == code))
    if region:
        return region
    region = Region(code=code, name=name)
    db.add(region)
    db.flush()
    return region


def get_or_create_user(db, login: str, display_name: str, role: UserRole, region=None) -> User:
    user = db.scalar(select(User).where(User.login == login))
    if user:
        return user
    user = User(login=login, display_name=display_name, role=role, region=region)
    db.add(user)
    db.flush()
    return user


def get_or_create_type(db, code: str, name: str, fields: list[dict]) -> EquipmentType:
    equipment_type = db.scalar(select(EquipmentType).where(EquipmentType.code == code))
    if equipment_type:
        return equipment_type

    equipment_type = EquipmentType(code=code, name=name)
    db.add(equipment_type)
    db.flush()

    for index, field in enumerate(fields, start=1):
        db.add(
            EquipmentTypeField(
                equipment_type=equipment_type,
                code=field["code"],
                name=field["name"],
                field_type=field["type"],
                is_required=field.get("required", False),
                is_filterable=field.get("filterable", False),
                display_order=index,
                options=field.get("options", []),
                validation_rules=field.get("validation_rules", {}),
            )
        )
    db.flush()
    return equipment_type


def add_equipment_if_empty(db, region, user, equipment_type, title, **kwargs) -> None:
    exists = db.scalar(select(Equipment).where(Equipment.title == title, Equipment.region == region))
    if exists:
        return
    db.add(
        Equipment(
            region=region,
            equipment_type=equipment_type,
            title=title,
            created_by_user_id=user.id,
            updated_by_user_id=user.id,
            **kwargs,
        )
    )


def main() -> None:
    with SessionLocal() as db:
        center_region = get_or_create_region(db, "CENTER", "Центр")
        region_24 = get_or_create_region(db, "R24", "Регион 24")
        region_08 = get_or_create_region(db, "R08", "Регион 08")
        region_31 = get_or_create_region(db, "R31", "Регион 31")

        center_user = get_or_create_user(db, "center", "Пользователь центра", UserRole.center)
        region_24_user = get_or_create_user(
            db, "region24", "Оператор региона 24", UserRole.region, region_24
        )
        region_08_user = get_or_create_user(
            db, "region08", "Оператор региона 08", UserRole.region, region_08
        )
        region_31_user = get_or_create_user(
            db, "region31", "Оператор региона 31", UserRole.region, region_31
        )

        laptop = get_or_create_type(
            db,
            "laptop",
            "Ноутбук",
            [
                {"code": "cpu", "name": "Процессор", "type": EquipmentFieldType.string},
                {
                    "code": "ram_gb",
                    "name": "ОЗУ, ГБ",
                    "type": EquipmentFieldType.integer,
                    "filterable": True,
                },
                {
                    "code": "condition_grade",
                    "name": "Состояние корпуса",
                    "type": EquipmentFieldType.select,
                    "options": ["Отличное", "Хорошее", "С дефектами"],
                },
            ],
        )
        mfp = get_or_create_type(
            db,
            "mfp",
            "МФУ",
            [
                {
                    "code": "page_count",
                    "name": "Пробег, страниц",
                    "type": EquipmentFieldType.integer,
                    "filterable": True,
                },
                {"code": "cartridge", "name": "Картридж", "type": EquipmentFieldType.string},
            ],
        )
        server = get_or_create_type(
            db,
            "server",
            "Сервер",
            [
                {"code": "cpu_count", "name": "CPU, шт.", "type": EquipmentFieldType.integer},
                {"code": "ram_gb", "name": "ОЗУ, ГБ", "type": EquipmentFieldType.integer},
                {"code": "disk_config", "name": "Диски", "type": EquipmentFieldType.text},
            ],
        )

        add_equipment_if_empty(
            db,
            region_24,
            region_24_user,
            laptop,
            "Lenovo ThinkPad T14",
            status=EquipmentStatus.valuation_pending,
            condition=EquipmentCondition.working,
            disposition=EquipmentDisposition.valuation,
            sale_status=EquipmentSaleStatus.valuation_pending,
            inventory_number="INV-24018",
            serial_number="PF3A91",
            completeness="Ноутбук, блок питания",
            attributes={"cpu": "Intel Core i5", "ram_gb": 16, "condition_grade": "Хорошее"},
        )
        add_equipment_if_empty(
            db,
            region_08,
            region_08_user,
            mfp,
            "Kyocera ECOSYS M2040dn",
            status=EquipmentStatus.writeoff_review,
            condition=EquipmentCondition.broken,
            disposition=EquipmentDisposition.writeoff,
            inventory_number="INV-08177",
            defect_description="Не включается, повреждён корпус, отсутствует лоток подачи.",
            attributes={"page_count": 218000, "cartridge": "TK-1170"},
        )
        add_equipment_if_empty(
            db,
            region_31,
            region_31_user,
            server,
            "Dell PowerEdge R740",
            status=EquipmentStatus.sale_ready,
            condition=EquipmentCondition.working,
            disposition=EquipmentDisposition.sale,
            sale_status=EquipmentSaleStatus.ready,
            inventory_number="INV-31004",
            serial_number="CN7791",
            valuation_amount=Decimal("185000.00"),
            sale_price=Decimal("170000.00"),
            sale_description="Рабочий сервер Dell PowerEdge R740, готов к продаже.",
            attributes={"cpu_count": 2, "ram_gb": 192, "disk_config": "8x 1.2TB SAS"},
        )

        # Kept to make explicit that center user exists for future workflow ownership.
        _ = center_region, center_user
        db.commit()


if __name__ == "__main__":
    main()
