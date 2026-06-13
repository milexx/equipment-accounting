from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import settings
from app.models.enums import EquipmentPhotoPurpose


@dataclass(frozen=True)
class StoredPhoto:
    id: UUID
    original_path: str
    thumbnail_path: str
    original_filename: str | None
    content_type: str
    file_size: int
    width: int
    height: int
    purpose: EquipmentPhotoPurpose


class PhotoStorage:
    allowed_content_types = {"image/jpeg", "image/png", "image/webp"}

    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.photo_root).resolve()
        self.max_size = settings.max_photo_size_mb * 1024 * 1024

    async def save_upload(
        self,
        *,
        equipment_id: int,
        upload: UploadFile,
        purpose: EquipmentPhotoPurpose,
    ) -> StoredPhoto | None:
        if not upload.filename:
            return None
        if upload.content_type not in self.allowed_content_types:
            raise ValueError("Можно загрузить только JPG, PNG или WEBP.")

        content = await upload.read()
        if not content:
            return None
        if len(content) > self.max_size:
            raise ValueError(f"Размер одного фото не должен превышать {settings.max_photo_size_mb} МБ.")

        photo_id = uuid4()
        photo_dir = self.root / str(equipment_id)
        photo_dir.mkdir(parents=True, exist_ok=True)

        try:
            image = Image.open(BytesIO(content))
        except UnidentifiedImageError as exc:
            raise ValueError("Файл не является корректным изображением.") from exc

        image = ImageOps.exif_transpose(image)
        width, height = image.size
        extension = self._extension(upload.content_type)
        original_file = photo_dir / f"{photo_id}{extension}"
        thumbnail_file = photo_dir / f"{photo_id}_thumb.jpg"

        original_file.write_bytes(content)
        self._save_thumbnail(image, thumbnail_file)

        return StoredPhoto(
            id=photo_id,
            original_path=self._public_path(original_file),
            thumbnail_path=self._public_path(thumbnail_file),
            original_filename=upload.filename,
            content_type=upload.content_type,
            file_size=len(content),
            width=width,
            height=height,
            purpose=purpose,
        )

    def _save_thumbnail(self, image: Image.Image, path: Path) -> None:
        thumbnail = image.convert("RGB")
        thumbnail.thumbnail((360, 360))
        thumbnail.save(path, "JPEG", quality=82, optimize=True)

    def _extension(self, content_type: str) -> str:
        if content_type == "image/png":
            return ".png"
        if content_type == "image/webp":
            return ".webp"
        return ".jpg"

    def _public_path(self, path: Path) -> str:
        relative = path.relative_to(self.root)
        return f"/media/photos/{relative.as_posix()}"
