import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings


class LocalStorage:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def save_upload(self, upload: UploadFile, subdir: str) -> tuple[Path, bytes]:
        target_dir = self.settings.storage_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(upload.filename or "").suffix
        destination = target_dir / f"{uuid.uuid4()}{suffix}"
        content = await upload.read()
        destination.write_bytes(content)
        await upload.seek(0)
        return destination, content

    @staticmethod
    def checksum(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()
