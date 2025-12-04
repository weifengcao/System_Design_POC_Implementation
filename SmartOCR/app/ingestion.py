from __future__ import annotations

from typing import Optional

MAX_SIZE_BYTES = 20 * 1024 * 1024  # 20MB limit per PRD
ALLOWED_CONTENT_TYPES = {"application/pdf", "image/png", "image/jpeg"}


def validate_upload(content: Optional[bytes], content_type: Optional[str]) -> None:
    if not content:
        raise ValueError("Empty upload")
    if len(content) > MAX_SIZE_BYTES:
        raise ValueError("File exceeds 20MB limit")
    if content_type and content_type.lower() not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Unsupported content type")


class ObjectStore:
    """
    Placeholder for object storage interactions; swap with S3/MinIO client.
    """

    def __init__(self) -> None:
        self._mem = {}

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._mem[key] = data
        return f"mem://{key}"

    def get(self, key: str) -> Optional[bytes]:
        return self._mem.get(key)
