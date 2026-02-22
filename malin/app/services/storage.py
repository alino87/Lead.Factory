"""
S3/MinIO storage service for document files.
"""

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
    """Create the bucket if it doesn't exist."""
    client = _get_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        try:
            client.create_bucket(Bucket=settings.s3_bucket)
            logger.info(f"Created S3 bucket: {settings.s3_bucket}")
        except ClientError as e:
            raise StorageError(f"Cannot create bucket: {e}")


def upload_file(data: bytes, content_type: str, tenant_id: uuid.UUID, filename: str) -> str:
    """Upload a file and return its S3 key."""
    client = _get_client()
    s3_key = f"{tenant_id}/{uuid.uuid4()}/{filename}"
    try:
        client.put_object(
            Bucket=settings.s3_bucket,
            Key=s3_key,
            Body=io.BytesIO(data),
            ContentType=content_type,
        )
    except ClientError as e:
        raise StorageError(f"Upload failed: {e}")
    return s3_key
