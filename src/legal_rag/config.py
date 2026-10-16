"""Read project settings and resolve local paths for the source checkout."""

from dataclasses import dataclass
from pathlib import Path
import re

import yaml


# This project currently uses an editable installation of the src/ package.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class DatasetConfig:
    repo_id: str
    revision: str
    files: dict[str, str]


@dataclass(frozen=True)
class PathsConfig:
    raw_dir: Path


@dataclass(frozen=True)
class ProjectConfig:
    dataset: DatasetConfig
    paths: PathsConfig


def _require_mapping(value: object, field: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a YAML mapping (key: value).")
    return value


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value.strip()


def _resolve_local_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def load_config(config_path: str | Path = "configs/project.yaml") -> ProjectConfig:
    """Load the settings required for downloading the source dataset.

    Relative config and output paths are resolved against PROJECT_ROOT,
    regardless of the terminal's current directory. Absolute paths are also
    accepted. This function reads settings only; it creates no directories
    and downloads no files.
    """
    path = _resolve_local_path(config_path)
    try:
        with path.open(encoding="utf-8") as file:
            contents = yaml.safe_load(file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Configuration file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

    root = _require_mapping(contents, "config")
    dataset = _require_mapping(root.get("dataset"), "dataset")
    repo_id = _require_string(dataset.get("repo_id"), "dataset.repo_id")
    revision = _require_string(dataset.get("revision"), "dataset.revision")
    if re.fullmatch(r"[0-9a-fA-F]{40}", revision) is None:
        raise ValueError("dataset.revision must be a full 40-character commit SHA.")

    source_files = _require_mapping(dataset.get("files"), "dataset.files")
    files = {
        name: _require_string(source_files.get(name), f"dataset.files.{name}")
        for name in ("metadata", "content", "relationships")
    }

    paths = _require_mapping(root.get("paths"), "paths")
    raw_dir = _require_string(paths.get("raw_dir"), "paths.raw_dir")

    return ProjectConfig(
        dataset=DatasetConfig(repo_id=repo_id, revision=revision, files=files),
        paths=PathsConfig(raw_dir=_resolve_local_path(raw_dir)),
    )
