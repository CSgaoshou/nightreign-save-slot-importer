import zipfile
import logging
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def create_backup(save_file: str | Path, backup_dir: str | Path, max_backups=5):
    save_path = Path(save_file)
    backup_dir = Path(backup_dir)
    internal_bak = save_path.with_suffix(save_path.suffix + ".tmp")

    if not save_path.exists():
        yield
        return

    save_path.replace(internal_bak)
    try:
        yield
    except Exception as e:
        logger.info("Restoring original file from internal backup...")
        internal_bak.replace(save_path)
        raise e

    backup_dir.mkdir(parents=True, exist_ok=True)
    root_zip = backup_dir / "root.zip"
    if not root_zip.exists():
        output_zip = root_zip
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_zip = backup_dir / f"backup_{timestamp}.zip"

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(internal_bak, arcname=save_path.name)
    logger.info(f"Created new backup: {output_zip.name}")

    if output_zip != root_zip:
        _rotate_backups(backup_dir, max_backups)

    internal_bak.unlink()


def _rotate_backups(backup_dir: Path, max_backups: int) -> None:
    backups = sorted(list(backup_dir.glob("backup_*.zip")))
    if len(backups) <= max_backups:
        return
    excess_count = len(backups) - max_backups
    for i in range(excess_count):
        old_backup = backups[i]
        old_backup.unlink(missing_ok=True)
        logger.info(f"Removed old backup: {old_backup.name}")
