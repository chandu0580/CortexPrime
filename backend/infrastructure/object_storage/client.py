from __future__ import annotations

import io
import logging
import os
from pathlib import PurePosixPath
from typing import AsyncIterator, Optional

log = logging.getLogger(__name__)

try:
    import s3fs
    _S3FS_AVAILABLE = True
except ImportError:
    _S3FS_AVAILABLE = False

_ARTIFACTS_BUCKET: str = "cortex-artifacts"
_LOGS_BUCKET: str = "cortex-logs"
_BACKUPS_BUCKET: str = "cortex-backups"


class ObjectStorageClient:
    def __init__(self) -> None:
        self._fs: Optional[s3fs.S3FileSystem] = None
        self._available: bool = False
        self._endpoint: str = ""

    async def connect(self) -> bool:
        if not _S3FS_AVAILABLE:
            log.warning("s3fs not installed — object storage disabled")
            return False
        endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        access_key = os.getenv("MINIO_ACCESS_KEY", "cortex")
        secret_key = os.getenv("MINIO_SECRET_KEY", "")
        secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

        try:
            self._fs = s3fs.S3FileSystem(
                key=access_key,
                secret=secret_key,
                endpoint_url=f"{'https' if secure else 'http'}://{endpoint}",
                use_ssl=secure,
                client_kwargs={"verify": False} if not secure else {},
            )
            await self._ensure_buckets()
            self._available = True
            self._endpoint = endpoint
            log.info("Object storage connected (%s)", endpoint)
            return True
        except Exception as exc:
            log.warning("Object storage connect failed: %s", exc)
            self._available = False
            return False

    async def _ensure_buckets(self):
        for bucket in [_ARTIFACTS_BUCKET, _LOGS_BUCKET, _BACKUPS_BUCKET]:
            try:
                if not self._fs.exists(bucket):
                    self._fs.mkdir(bucket)
                    log.info("Created bucket: %s", bucket)
            except Exception as exc:
                log.warning("Bucket %s creation failed: %s", bucket, exc)

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    async def upload_artifact(
        self, mission_id: str, filename: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        key = f"{mission_id}/{filename}"
        path = f"{_ARTIFACTS_BUCKET}/{key}"
        try:
            with self._fs.open(path, "wb") as f:
                f.write(data)
            log.info("Artifact uploaded: %s (%d bytes)", path, len(data))
            return key
        except Exception as exc:
            log.error("Artifact upload failed: %s", exc)
            raise

    async def download_artifact(self, mission_id: str, filename: str) -> Optional[bytes]:
        path = f"{_ARTIFACTS_BUCKET}/{mission_id}/{filename}"
        try:
            with self._fs.open(path, "rb") as f:
                return f.read()
        except FileNotFoundError:
            return None
        except Exception as exc:
            log.error("Artifact download failed: %s", exc)
            return None

    async def list_artifacts(self, mission_id: str, prefix: str = "") -> list[str]:
        base = f"{_ARTIFACTS_BUCKET}/{mission_id}/{prefix}"
        try:
            return [str(PurePosixPath(p).relative_to(f"{_ARTIFACTS_BUCKET}/{mission_id}")) for p in self._fs.glob(f"{base}*") if self._fs.isfile(p)]
        except Exception:
            return []

    async def delete_artifact(self, mission_id: str, filename: str) -> bool:
        path = f"{_ARTIFACTS_BUCKET}/{mission_id}/{filename}"
        try:
            self._fs.rm(path)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    async def upload_log(self, execution_id: str, log_name: str, data: bytes) -> str:
        key = f"{execution_id}/{log_name}"
        path = f"{_LOGS_BUCKET}/{key}"
        try:
            with self._fs.open(path, "wb") as f:
                f.write(data)
            return key
        except Exception as exc:
            log.error("Log upload failed: %s", exc)
            raise

    async def stream_log(self, execution_id: str, log_name: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        path = f"{_LOGS_BUCKET}/{execution_id}/{log_name}"
        try:
            with self._fs.open(path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except Exception:
            return

    # ------------------------------------------------------------------
    # Backups
    # ------------------------------------------------------------------

    async def upload_backup(self, name: str, data: bytes) -> str:
        path = f"{_BACKUPS_BUCKET}/{name}"
        try:
            with self._fs.open(path, "wb") as f:
                f.write(data)
            return name
        except Exception as exc:
            log.error("Backup upload failed: %s", exc)
            raise

    async def list_backups(self) -> list[str]:
        try:
            return [str(PurePosixPath(p).relative_to(_BACKUPS_BUCKET)) for p in self._fs.glob(f"{_BACKUPS_BUCKET}/*")]
        except Exception:
            return []

    async def delete_backup(self, name: str) -> bool:
        path = f"{_BACKUPS_BUCKET}/{name}"
        try:
            self._fs.rm(path)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        self._fs = None
        self._available = False
        log.info("Object storage client closed")

    @property
    def is_available(self) -> bool:
        return self._available


object_storage = ObjectStorageClient()
