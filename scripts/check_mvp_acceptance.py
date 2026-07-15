from __future__ import annotations

import asyncio
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) in sys.path:
    sys.path.remove(str(SCRIPT_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if __name__ == "__main__":
    print(
        "Run acceptance checks with:\n"
        ".venv/bin/python -c "
        '"from scripts.check_mvp_acceptance import main; raise SystemExit(main())"'
    )
    raise SystemExit(2)

from PIL import Image  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402
from starlette.datastructures import Headers  # noqa: E402

from app.api.equipment import save_uploaded_photos  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.media_storage.photo_storage import PhotoStorage  # noqa: E402
from app.models.audit import EquipmentAuditLog  # noqa: E402
from app.models.enums import EquipmentCondition, EquipmentPhotoPurpose, EquipmentStatus  # noqa: E402
from app.models.equipment import Equipment  # noqa: E402
from app.models.equipment_type import EquipmentType  # noqa: E402
from app.models.photo import EquipmentPhoto  # noqa: E402
from app.models.region import Region  # noqa: E402
from app.schemas.equipment import EquipmentCreateData, EquipmentUpdateData  # noqa: E402
from app.services.equipment_service import EquipmentService  # noqa: E402


BASE_URL = "http://127.0.0.1:8010"
TEST_PREFIX = "MVP_ACCEPTANCE_"


@dataclass
class CheckResult:
    name: str
    detail: str


class FakeUpload:
    def __init__(self, filename: str, content_type: str, content: bytes) -> None:
        self.filename = filename
        self.headers = Headers({"content-type": content_type})
        self.content_type = content_type
        self._content = content

    async def read(self) -> bytes:
        return self._content


def main() -> int:
    results: list[CheckResult] = []
    created_ids: list[int] = []

    try:
        cleanup_acceptance_data()
        results.extend(check_http_smoke())
        results.extend(check_access_rules())
        duplicate_id = check_duplicate_submit()
        created_ids.append(duplicate_id)
        results.append(CheckResult("duplicate submit", f"повторная отправка вернула id={duplicate_id}"))
        conflict_id = check_row_version_conflict()
        created_ids.append(conflict_id)
        results.append(CheckResult("row_version conflict", f"устаревшая версия отклонена для id={conflict_id}"))
        photo_id = check_photo_upload_delete()
        created_ids.append(photo_id)
        results.append(CheckResult("photo upload/delete", f"фото добавлено и удалено для id={photo_id}"))
        mass_ids = check_parallel_create_and_center_list()
        created_ids.extend(mass_ids)
        results.append(CheckResult("60 parallel creates", f"создано {len(mass_ids)} карточек"))
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    finally:
        cleanup_acceptance_data()

    for result in results:
        print(f"OK: {result.name} - {result.detail}")
    print("MVP acceptance checks passed")
    return 0


def check_http_smoke() -> list[CheckResult]:
    checks = [
        ("health", "/health", None, 200, '"status":"ok"'),
        ("home", "/", None, 200, "Учёт неиспользуемого оборудования"),
        ("login", "/login", None, 200, "Администратор центра"),
        ("region", "/region", "demo_user=region24", 200, "Рабочее место филиала"),
        ("equipment list", "/equipment", "demo_user=center", 200, "Реестр оборудования"),
        ("pricing", "/pricing", "demo_user=center", 200, "Оценщик"),
        ("equipment new", "/equipment/new", "demo_user=region24", 200, "Добавить оборудование"),
        ("equipment detail", "/equipment/1", "demo_user=center", 200, "Lenovo ThinkPad T14"),
        ("documentation", "/documentation", None, 200, "Бизнес-процесс системы"),
    ]
    return [
        CheckResult(name, f"{path} вернул {status}")
        for name, path, cookie, status, expected in checks
        if http_get(path, cookie=cookie, expected_status=status, expected_text=expected) is not None
    ]


def check_access_rules() -> list[CheckResult]:
    http_get("/equipment", cookie="demo_user=region24", expected_status=403)
    http_get("/pricing", cookie="demo_user=region24", expected_status=403)
    http_get("/admin", cookie="demo_user=center", expected_status=403)
    http_get("/admin", cookie="demo_user=admin", expected_status=200, expected_text="Администрирование")
    http_get("/equipment/2", cookie="demo_user=region24", expected_status=403)
    return [
        CheckResult("region cannot open center registry", "/equipment вернул 403"),
        CheckResult("region cannot open pricing", "/pricing вернул 403"),
        CheckResult("center cannot open admin", "/admin для center вернул 403"),
        CheckResult("admin can open admin", "/admin для admin вернул 200"),
        CheckResult("region isolation", "region24 не видит карточку другого региона"),
    ]


def check_duplicate_submit() -> int:
    with SessionLocal() as db:
        region, equipment_type = get_base_refs(db)
        title = f"{TEST_PREFIX}duplicate"
        data = EquipmentCreateData(
            region_id=region.id,
            equipment_type_id=equipment_type.id,
            title=title,
            location="acceptance-room",
            condition=EquipmentCondition.working,
            status=EquipmentStatus.submitted,
            inventory_number=f"{TEST_PREFIX}INV-DUP",
            serial_number=f"{TEST_PREFIX}SN-DUP",
            comment="duplicate submit acceptance check",
        )
        first = EquipmentService(db).create_equipment(data)
        second = EquipmentService(db).create_equipment(data)
        if first.id != second.id:
            raise AssertionError("duplicate submit created two different records")
        return first.id


def check_row_version_conflict() -> int:
    with SessionLocal() as db:
        item = create_test_equipment(db, "row-version")
        stale_version = item.row_version
        service = EquipmentService(db)
        service.update_equipment(
            item.id,
            EquipmentUpdateData(
                title=item.title,
                location="acceptance-room-updated",
                condition=item.condition,
                row_version=stale_version,
                comment="first update",
            ),
        )
        try:
            service.update_equipment(
                item.id,
                EquipmentUpdateData(
                    title=item.title,
                    location="acceptance-room-stale",
                    condition=item.condition,
                    row_version=stale_version,
                    comment="stale update",
                ),
            )
        except ValueError as exc:
            if "Карточку уже изменили" not in str(exc):
                raise
            return item.id
        raise AssertionError("stale row_version update was accepted")


def check_photo_upload_delete() -> int:
    with SessionLocal() as db:
        item = create_test_equipment(db, "photo")
        upload = FakeUpload("acceptance.png", "image/png", make_png())
        photos = asyncio.run(
            save_uploaded_photos(
                db,
                item.id,
                {EquipmentPhotoPurpose.general: [upload]},
            )
        )
        if len(photos) != 1:
            raise AssertionError("photo upload did not create one photo")
        photo = photos[0]
        if not photo.original_path or not photo.thumbnail_path:
            raise AssertionError("photo paths were not saved")
        PhotoStorage().delete_paths([photo.original_path, photo.thumbnail_path])
        db.execute(delete(EquipmentPhoto).where(EquipmentPhoto.id == photo.id))
        db.commit()
        remaining = db.scalar(select(EquipmentPhoto).where(EquipmentPhoto.id == photo.id))
        if remaining is not None:
            raise AssertionError("photo delete did not remove database record")
        return item.id


def check_parallel_create_and_center_list() -> list[int]:
    suffix = uuid4().hex[:8]
    created_ids: list[int] = []
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = [executor.submit(create_parallel_item, suffix, index) for index in range(60)]
        time.sleep(0.2)
        http_get("/equipment", cookie="demo_user=center", expected_status=200, expected_text="Реестр")
        for future in as_completed(futures):
            created_ids.append(future.result())
    if len(set(created_ids)) != 60:
        raise AssertionError("parallel create returned duplicate ids")
    return created_ids


def create_parallel_item(suffix: str, index: int) -> int:
    with SessionLocal() as db:
        item = create_test_equipment(db, f"parallel-{suffix}-{index:02d}")
        return item.id


def create_test_equipment(db, suffix: str) -> Equipment:
    region, equipment_type = get_base_refs(db)
    service = EquipmentService(db)
    return service.create_equipment(
        EquipmentCreateData(
            region_id=region.id,
            equipment_type_id=equipment_type.id,
            title=f"{TEST_PREFIX}{suffix}",
            location="acceptance-room",
            condition=EquipmentCondition.working,
            status=EquipmentStatus.submitted,
            inventory_number=f"{TEST_PREFIX}INV-{suffix}",
            serial_number=f"{TEST_PREFIX}SN-{suffix}",
            comment="MVP acceptance check",
        )
    )


def get_base_refs(db) -> tuple[Region, EquipmentType]:
    region = db.scalar(select(Region).where(Region.is_active.is_(True)).order_by(Region.id))
    equipment_type = db.scalar(
        select(EquipmentType).where(EquipmentType.is_active.is_(True)).order_by(EquipmentType.id)
    )
    if region is None or equipment_type is None:
        raise AssertionError("seed data is required: active region and equipment type not found")
    return region, equipment_type


def cleanup_acceptance_data() -> None:
    with SessionLocal() as db:
        ids = list(db.scalars(select(Equipment.id).where(Equipment.title.like(f"{TEST_PREFIX}%"))))
        if not ids:
            return
        photos = list(
            db.scalars(select(EquipmentPhoto).where(EquipmentPhoto.equipment_id.in_(ids)))
        )
        for photo in photos:
            PhotoStorage().delete_paths([photo.original_path, photo.thumbnail_path])
        db.execute(delete(EquipmentAuditLog).where(EquipmentAuditLog.equipment_id.in_(ids)))
        db.execute(delete(EquipmentPhoto).where(EquipmentPhoto.equipment_id.in_(ids)))
        db.execute(delete(Equipment).where(Equipment.id.in_(ids)))
        db.commit()


def http_get(
    path: str,
    *,
    cookie: str | None = None,
    expected_status: int,
    expected_text: str | None = None,
) -> str:
    request = urllib.request.Request(f"{BASE_URL}{path}")
    if cookie:
        request.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = response.status
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise AssertionError(f"{BASE_URL} is not available: {exc}") from exc

    if status != expected_status:
        raise AssertionError(f"{path} returned {status}, expected {expected_status}")
    if expected_text and expected_text not in body:
        raise AssertionError(f"{path} did not contain expected text: {expected_text}")
    return body


def make_png() -> bytes:
    buffer = BytesIO()
    image = Image.new("RGB", (16, 16), color=(12, 90, 140))
    image.save(buffer, format="PNG")
    return buffer.getvalue()
