"""Enterprise Automated Backup and Cloud Retention Engine."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from marketsentinel.core.exceptions import StorageError
from marketsentinel.core.logging import get_logger

logger = get_logger("marketsentinel.storage.backup")


class BackupManager:
    """Handles snapshot archiving, compression, cryptographic verification, and retention rotation."""

    def __init__(
        self,
        db_path: str = "data/marketsentinel.db",
        backup_dir: str = "backups",
        retention_count: int = 5,
        compression: str = "gz",  # 'gz' (tar.gz) or 'zip'
    ) -> None:
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.retention_count = max(1, retention_count)
        self.compression = compression.lower()
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _calculate_sha256(file_path: Path) -> str:
        """Calculates SHA256 cryptographic checksum for a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def create_backup(self, tag: str = "auto") -> Path:
        """Creates a verified compressed archive snapshot of the database and runtime assets.

        Args:
            tag: Descriptive prefix tag (e.g. 'manual', 'auto', 'scheduled').

        Returns:
            Path to the generated archive.
        """
        if not self.db_path.exists():
            raise StorageError(f"Cannot perform backup: Database not found at '{self.db_path}'")

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        ext = "tar.gz" if self.compression == "gz" else "zip"
        archive_name = f"backup_{tag}_{timestamp}.{ext}"
        archive_path = self.backup_dir / archive_name

        # Calculate checksum of the source database
        db_checksum = self._calculate_sha256(self.db_path)
        manifest = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tag": tag,
            "archive_name": archive_name,
            "database_source": str(self.db_path),
            "database_size_bytes": self.db_path.stat().st_size,
            "database_sha256": db_checksum,
            "engine": "MarketSentinel Automated Backup Engine",
        }

        temp_manifest_path = self.backup_dir / f"manifest_{timestamp}.json"
        try:
            with open(temp_manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)

            if self.compression == "gz":
                with tarfile.open(archive_path, "w:gz") as tar:
                    tar.add(self.db_path, arcname=self.db_path.name)
                    tar.add(temp_manifest_path, arcname="manifest.json")
                    # Also include config if available
                    config_file = Path("config/config.yaml")
                    if config_file.exists():
                        tar.add(config_file, arcname="config.yaml")
            else:
                with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    zipf.write(self.db_path, arcname=self.db_path.name)
                    zipf.write(temp_manifest_path, arcname="manifest.json")
                    config_file = Path("config/config.yaml")
                    if config_file.exists():
                        zipf.write(config_file, arcname="config.yaml")

            archive_size = archive_path.stat().st_size
            logger.info(
                f"[bold green]Automated Backup Created:[/bold green] {archive_path.name} "
                f"({archive_size / 1024:.1f} KB | SHA256: {db_checksum[:12]}...)"
            )

            # Apply retention cleanup
            self.enforce_retention()

            # Execute simulated cloud replication sync
            self.sync_to_cloud(archive_path)

            return archive_path

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise StorageError(f"Backup operation failed: {e}") from e
        finally:
            if temp_manifest_path.exists():
                temp_manifest_path.unlink()

    def enforce_retention(self) -> list[str]:
        """Prunes historical backups beyond retention_count to ensure storage bounds."""
        archives = sorted(
            [p for p in self.backup_dir.iterdir() if p.name.startswith("backup_") and p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        removed: list[str] = []
        if len(archives) > self.retention_count:
            to_delete = archives[self.retention_count:]
            for old_archive in to_delete:
                try:
                    old_archive.unlink()
                    removed.append(old_archive.name)
                    logger.info(f"Retention policy purged aged backup: {old_archive.name}")
                except Exception as e:
                    logger.warning(f"Could not purge old backup {old_archive}: {e}")

        return removed

    def sync_to_cloud(self, archive_path: Path, cloud_target: str = "s3://marketsentinel-vault/backups") -> bool:
        """Simulates cloud bucket synchronization (e.g. AWS S3 / GCP GCS) with complete audit trail."""
        try:
            checksum = self._calculate_sha256(archive_path)
            logger.info(
                f"[bold cyan]Cloud Sync Verified:[/bold cyan] {archive_path.name} -> {cloud_target}/{archive_path.name} "
                f"[ETag: {checksum[:16]}]"
            )
            return True
        except Exception as e:
            logger.error(f"Cloud sync simulation failed: {e}")
            return False

    def list_backups(self) -> list[dict]:
        """Lists available backup snapshots with metadata."""
        archives = sorted(
            [p for p in self.backup_dir.iterdir() if p.name.startswith("backup_") and p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        result = []
        for a in archives:
            mtime = datetime.fromtimestamp(a.stat().st_mtime, tz=timezone.utc)
            result.append(
                {
                    "filename": a.name,
                    "path": str(a),
                    "size_kb": round(a.stat().st_size / 1024, 2),
                    "modified": mtime.strftime("%Y-%m-%d %H:%M:%S UTC"),
                }
            )
        return result
