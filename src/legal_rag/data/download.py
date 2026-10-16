"""Download the pinned source files and record their local metadata."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from huggingface_hub import hf_hub_download
from huggingface_hub.errors import LocalEntryNotFoundError
import pyarrow.parquet as pq

from legal_rag.config import ProjectConfig


def _sha256(path: Path) -> str:
    """Hash a file in small blocks instead of loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _get_source_file(config: ProjectConfig, remote_path: str) -> Path:
    """Use an exact-revision cache entry first; download if it is missing."""
    arguments = {
        "repo_id": config.dataset.repo_id,
        "repo_type": "dataset",
        "revision": config.dataset.revision,
        "filename": remote_path,
    }
    try:
        cached = hf_hub_download(**arguments, local_files_only=True)
        print("  Found the source file in the Hugging Face cache.", flush=True)
    except LocalEntryNotFoundError:
        print("  Downloading the source file from Hugging Face...", flush=True)
        cached = hf_hub_download(**arguments)
    return Path(cached)


def _copy_if_needed(source: Path, destination: Path, checksum: str) -> None:
    """Replace the destination only after a complete, verified copy exists."""
    if (
        destination.is_file()
        and destination.stat().st_size == source.stat().st_size
        and _sha256(destination) == checksum
    ):
        print("  The local copy already matches; skipping the copy.", flush=True)
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp", delete=False
    ) as file:
        temporary = Path(file.name)
    try:
        shutil.copyfile(source, temporary)
        if _sha256(temporary) != checksum:
            raise ValueError("The copied file does not match the source checksum.")
        pq.read_metadata(temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _write_manifest(path: Path, manifest: dict) -> None:
    """Write a complete JSON file before replacing the previous manifest."""
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=".manifest.", suffix=".tmp", delete=False
    ) as file:
        temporary = Path(file.name)
        try:
            json.dump(manifest, file, ensure_ascii=False, indent=2)
            file.write("\n")
        except BaseException:
            file.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def download_data(config: ProjectConfig) -> dict[str, Path]:
    """Download all configured source files, without selecting or cleaning rows.

    Returns a mapping from source name to its local Parquet path. Cache files
    are copied, not moved, so the output remains independent of the cache.
    The final manifest is written only after every source file is valid.
    """
    raw_dir = config.paths.raw_dir
    raw_dir.mkdir(parents=True, exist_ok=True)
    local_paths: dict[str, Path] = {}
    file_records = {}

    print(f"Dataset: {config.dataset.repo_id}", flush=True)
    print(f"Revision: {config.dataset.revision}", flush=True)
    print(f"Output directory: {raw_dir}", flush=True)

    for name, remote_path in config.dataset.files.items():
        print(f"\nProcessing {name}: {remote_path}", flush=True)
        try:
            source = _get_source_file(config, remote_path)
            metadata = pq.read_metadata(source)
            checksum = _sha256(source)
            destination = raw_dir / name / Path(remote_path).name
            _copy_if_needed(source, destination, checksum)

            file_records[name] = {
                "remote_path": remote_path,
                "local_path": str(destination),
                "size_bytes": destination.stat().st_size,
                "num_rows": metadata.num_rows,
                "sha256": checksum,
            }
            local_paths[name] = destination
            print(f"  Ready: {destination} ({metadata.num_rows:,} rows)", flush=True)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to prepare '{name}' from '{remote_path}': {exc}"
            ) from exc

    manifest = {
        "repo_id": config.dataset.repo_id,
        "revision": config.dataset.revision,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": file_records,
    }
    manifest_path = raw_dir / "manifest.json"
    _write_manifest(manifest_path, manifest)
    print(f"\nAll source files are ready. Manifest: {manifest_path}", flush=True)
    return local_paths


if __name__ == "__main__":
    from legal_rag.config import load_config

    download_data(load_config())
