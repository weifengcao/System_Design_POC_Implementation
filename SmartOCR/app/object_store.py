from __future__ import annotations

from io import BytesIO

from minio import Minio

from .config import settings


class MinioDocumentStore:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket_name = settings.MINIO_BUCKET

    def save(self, doc_id: str, content: bytes) -> str:
        bucket_exists = self.client.bucket_exists(self.bucket_name)
        if not bucket_exists:
            self.client.make_bucket(self.bucket_name)

        self.client.put_object(
            self.bucket_name,
            doc_id,
            BytesIO(content),
            len(content),
        )
        return f"{self.bucket_name}/{doc_id}"

    def get(self, doc_id: str) -> bytes:
        response = self.client.get_object(self.bucket_name, doc_id)
        return response.read()
