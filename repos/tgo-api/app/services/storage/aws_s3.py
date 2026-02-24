"""AWS S3 storage backend."""

import asyncio
from typing import BinaryIO, Optional
from urllib.parse import urlparse

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None
    ClientError = Exception

from app.services.storage.base import StorageBackend


class AWSS3Backend(StorageBackend):
    """AWS S3 storage implementation."""

    def __init__(
        self,
        bucket_name: Optional[str],
        region_name: str = "us-east-1",
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        session_token: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        public_base_url: Optional[str] = None,
    ):
        """
        Initialize AWS S3 backend.

        Args:
            bucket_name: S3 bucket name
            region_name: AWS region (e.g., us-east-1)
            access_key_id: Optional AWS access key ID
            secret_access_key: Optional AWS secret access key
            session_token: Optional AWS session token (STS)
            endpoint_url: Optional custom S3 endpoint URL
            public_base_url: Optional public base URL (e.g., CloudFront domain)
        """
        if boto3 is None:
            raise ImportError(
                "The 'boto3' package is required for AWSS3Backend. "
                "Install it with 'pip install boto3'."
            )
        if not bucket_name:
            raise ValueError("AWS_S3_BUCKET_NAME is required when STORAGE_TYPE=s3")

        self.bucket_name: str = bucket_name
        self.region_name = (region_name or "us-east-1").strip()
        self.endpoint_url = endpoint_url.rstrip("/") if endpoint_url else None
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None

        client_kwargs: dict[str, str] = {
            "region_name": self.region_name,
        }
        if access_key_id:
            client_kwargs["aws_access_key_id"] = access_key_id
        if secret_access_key:
            client_kwargs["aws_secret_access_key"] = secret_access_key
        if session_token:
            client_kwargs["aws_session_token"] = session_token
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url

        self.s3 = boto3.client("s3", **client_kwargs)

    async def upload(self, file: BinaryIO, path: str, content_type: str) -> str:
        """Upload file to AWS S3."""
        loop = asyncio.get_event_loop()
        clean_path = path.lstrip("/")

        await loop.run_in_executor(
            None,
            lambda: self.s3.put_object(
                Bucket=self.bucket_name,
                Key=clean_path,
                Body=file,
                ContentType=content_type,
            ),
        )
        return self.get_public_url(path)

    async def delete(self, path: str) -> bool:
        """Delete file from AWS S3."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self.s3.delete_object(
                    Bucket=self.bucket_name,
                    Key=path.lstrip("/"),
                ),
            )
            return True
        except Exception:
            return False

    def get_public_url(self, path: str) -> str:
        """Get public URL for a file path."""
        clean_path = path.lstrip("/")

        if self.public_base_url:
            return f"{self.public_base_url}/{clean_path}"

        if self.endpoint_url:
            if self.bucket_name in self.endpoint_url:
                return f"{self.endpoint_url}/{clean_path}"
            return f"{self.endpoint_url}/{self.bucket_name}/{clean_path}"

        if self.region_name == "us-east-1":
            return f"https://{self.bucket_name}.s3.amazonaws.com/{clean_path}"
        return f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{clean_path}"

    async def exists(self, path: str) -> bool:
        """Check if file exists in AWS S3."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self.s3.head_object(
                    Bucket=self.bucket_name,
                    Key=path.lstrip("/"),
                ),
            )
            return True
        except ClientError:
            return False
        except Exception:
            return False

    def resolve_url(self, url: str) -> str:
        """
        Resolve and normalize a possibly relative or incorrect public URL.
        """
        if not url or not isinstance(url, str):
            return url

        if url.startswith("/"):
            path = url
            if path.startswith("/api/v1"):
                path = path[4:]
            return self.get_public_url(path)

        if url.startswith("http://") or url.startswith("https://"):
            parsed = urlparse(url)
            if "localhost" in parsed.netloc or "127.0.0.1" in parsed.netloc:
                path = parsed.path
                if path.startswith("/api/v1"):
                    path = path[4:]
                return self.get_public_url(path)

        return url

    def get_file_access_url(self, file_id: str, storage_url: str) -> str:
        """For cloud storage, return the direct storage URL."""
        return storage_url
