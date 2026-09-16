"""Object storage abstraction. MVP ships a local filesystem driver.

Swapping in S3/GCS later means implementing the same handful of methods.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from app.config import settings

_SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


class LocalStorage:
    def __init__(self, base_dir: Optional[str] = None) -> None:
        self.base = Path(base_dir or settings.storage_dir).resolve()
        self.base.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        if not key or not _SAFE_KEY_RE.match(key) or ".." in key.split("/"):
            raise ValueError(f"Invalid storage key: {key!r}")
        path = (self.base / key).resolve()
        # Defence in depth: never escape the storage root.
        if not str(path).startswith(str(self.base) + os.sep):
            raise ValueError(f"Storage key escapes base directory: {key!r}")
        return path

    def put_text(self, key: str, content: str) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return key

    def get_text(self, key: str) -> Optional[str]:
        path = self._resolve(key)
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def put_bytes(self, key: str, content: bytes) -> str:
        """Used for screenshots and any other binary artefact."""
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return key

    def get_bytes(self, key: str) -> Optional[bytes]:
        path = self._resolve(key)
        if not path.is_file():
            return None
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.is_file():
            path.unlink()


storage = LocalStorage()
