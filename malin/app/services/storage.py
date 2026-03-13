"""
S3/MinIO storage — SPEC §3.1 + §11 (signed URLs / backend streaming).
"""

import hashlib
import io
import logging
import uuid

import boto3
from botocore.exceptions import ClientError

from malin.app.config import settings
from malin.app.errors import StorageError

logger = logging.getLogger("malin.storage")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            use_ssl=settings.s3_use_ssl,
        )
    return _client


def ensure_bucket() -> None:
    client = _get_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        try:
            client.create_bucket(Bucket=settings.s3_bucket)
            logger.info(f"Created S3 bucket: {settings.s3_bucket}")
        except ClientError as e:
            raise StorageError(f"Cannot create bucket: {e}")


def compute_sha256(data: bytes) -> str:
    """SPEC §5.1 documents.sha256"""
    return hashlib.sha256(data).hexdigest()


def upload_file(data: bytes, mime_type: str, tenant_id: uuid.UUID, filename: str) -> str:
    client = _get_client()
    storage_key = f"{tenant_id}/{uuid.uuid4()}/{filename}"
    try:
        client.put_object(
            Bucket=settings.s3_bucket,
            Key=storage_key,
            Body=io.BytesIO(data),
            ContentType=mime_type,
        )
    except ClientError as e:
        raise StorageError(f"Upload failed: {e}")
    return storage_key


def download_file(storage_key: str) -> tuple[bytes, str]:
    client = _get_client()
    try:
        resp = client.get_object(Bucket=settings.s3_bucket, Key=storage_key)
        data = resp["Body"].read()
        content_type = resp.get("ContentType", "application/octet-stream")
        return data, content_type
    except ClientError as e:
        raise StorageError(f"Download failed: {e}")


def generate_presigned_url(storage_key: str, expires_in: int = 3600) -> str:
    """SPEC §11 — signed URL for secure streaming."""
    client = _get_client()
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": storage_key},
            ExpiresIn=expires_in,
        )
    except ClientError as e:
        raise StorageError(f"Cannot generate presigned URL: {e}")
