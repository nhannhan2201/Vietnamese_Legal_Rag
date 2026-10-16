"""Select a reproducible 200-document pilot from the downloaded source files."""

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import random
import re
import tempfile
import unicodedata

import pyarrow.parquet as pq

from legal_rag.config import PROJECT_ROOT, ProjectConfig


MIN_TEXT_CHARACTERS = 500
# Keys use normalized metadata labels. Scope is determined separately.
QUOTAS = {
    ("luật", "national"): 40,
    ("nghị định", "national"): 40,
    ("thông tư", "national"): 40,
    ("nghị quyết", "national"): 20,
    ("nghị quyết", "local"): 20,
    ("quyết định", "national"): 20,
    ("quyết định", "local"): 20,
}


def _normalize_label(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def _normalize_id(value: object) -> str:
    if value is None:
        raise ValueError("A source row has a missing document ID.")
    result = str(value).strip()
    if not result:
        raise ValueError("A source row has a blank document ID.")
    return result


def _group_for(metadata: dict) -> tuple[str, str] | None:
    if _normalize_label(metadata.get("tinh_trang_hieu_luc")) != "còn hiệu lực":
        return None
    kind = _normalize_label(metadata.get("loai_van_ban"))
    scope = _normalize_label(metadata.get("pham_vi"))
    if scope == "toàn quốc":
        group = (kind, "national")
    else:
        agency = _normalize_label(metadata.get("co_quan_ban_hanh"))
        local_agency = any(
            label in agency
            for label in ("ủy ban nhân dân", "uỷ ban nhân dân", "hội đồng nhân dân")
        ) or re.search(r"\b(?:ubnd|hđnd)\b", agency) is not None
        unknown_scopes = {"", "...", "…", "-", "chưa xác định", "không xác định"}
        if scope in unknown_scopes or not local_agency:
            return None
        group = (kind, "local")
    return group if group in QUOTAS else None


class _EnoughText(Exception):
    """Stop parsing once a document passes the preliminary length screen."""


class _TextScreen(HTMLParser):
    """Count visible non-whitespace characters, ignoring scripts and styles."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.count = 0
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style"):
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.hidden_depth:
            return
        self.count += sum(
            not character.isspace() and character not in "\u200b\ufeff"
            for character in data
        )
        if self.count >= MIN_TEXT_CHARACTERS:
            raise _EnoughText


def _screen_text(raw_html: str) -> str:
    """Return a screening reason, not cleaned text or a completeness judgment."""
    parser = _TextScreen()
    try:
        for offset in range(0, len(raw_html), 4096):
            parser.feed(raw_html[offset:offset + 4096])
        parser.close()
    except _EnoughText:
        return "eligible"
    return "empty_text" if parser.count == 0 else "short_text"


def _read_json(path: Path) -> object:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as file:
        temporary = Path(file.name)
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _choose_ids(candidates: dict, metadata: dict, seed: int) -> list[str]:
    pools = {group: [] for group in QUOTAS}
    for doc_id, group in candidates.items():
        pools[group].append(doc_id)
    shortages = [
        f"{kind}/{scope}: need {quota}, available {len(pools[(kind, scope)])}"
        for (kind, scope), quota in QUOTAS.items()
        if len(pools[(kind, scope)]) < quota
    ]
    if shortages:
        raise ValueError("Not enough eligible documents:\n" + "\n".join(shortages))

    rng = random.Random(seed)
    selected = []
    for group, quota in QUOTAS.items():
        pool = sorted(pools[group])
        if group[1] == "national":
            selected.extend(rng.sample(pool, quota))
            continue
        localities = defaultdict(list)
        for doc_id in pool:
            locality = _normalize_label(metadata[doc_id]["pham_vi"])
            localities[locality].append(doc_id)
        names = sorted(localities)
        for name in names:
            rng.shuffle(localities[name])
        rng.shuffle(names)
        group_selected = []
        while len(group_selected) < quota:
            for name in names:
                if localities[name]:
                    group_selected.append(localities[name].pop())
                    if len(group_selected) == quota:
                        break
        selected.extend(group_selected)
    return sorted(selected)


def _validate_ids(ids: object, candidates: dict) -> list[str]:
    if not isinstance(ids, list) or any(
        not isinstance(value, str) or not value or value != value.strip()
        for value in ids
    ):
        raise ValueError("The saved sample must be a JSON list of non-empty string IDs.")
    if len(ids) != 200 or len(set(ids)) != 200:
        raise ValueError("The saved sample must contain exactly 200 different IDs.")
    invalid = [doc_id for doc_id in ids if doc_id not in candidates]
    if invalid:
        raise ValueError(f"Saved IDs no longer meet the sampling rules: {invalid}")
    counts = Counter(candidates[doc_id] for doc_id in ids)
    if counts != Counter(QUOTAS):
        raise ValueError(f"The saved IDs do not match the required quotas: {dict(counts)}")
    return list(ids)


def select_sample(config: ProjectConfig, seed: int = 42) -> Path:
    """Select or reuse 200 IDs and export their original HTML and metadata.

    HTML screening is deliberately preliminary: passing the 500-character
    threshold does not prove completeness or current legal validity.
    Outputs are rooted in the source checkout, just like relative config paths.
    """
    raw_dir = config.paths.raw_dir
    output_dir = PROJECT_ROOT / "data/processed/sample_200"
    ids_path = PROJECT_ROOT / "configs/sample_200_ids.json"
    manifest_path = output_dir / "manifest.json"
    source_manifest = _read_json(raw_dir / "manifest.json")
    for field, expected in (
        ("repo_id", config.dataset.repo_id), ("revision", config.dataset.revision)
    ):
        if not isinstance(source_manifest, dict) or source_manifest.get(field) != expected:
            raise ValueError(f"The raw manifest does not match configured {field}.")
    previous = {}
    if ids_path.exists() and manifest_path.exists():
        previous = _read_json(manifest_path)
        if not isinstance(previous, dict) or any(
            previous.get(key) != source_manifest[key] for key in ("repo_id", "revision")
        ):
            raise ValueError("The existing sample belongs to a different dataset revision.")

    source_paths = {
        name: raw_dir / name / Path(config.dataset.files[name]).name
        for name in ("metadata", "content")
    }
    statistics = Counter()
    metadata = {}
    print("Reading metadata...", flush=True)
    for batch in pq.ParquetFile(source_paths["metadata"]).iter_batches(batch_size=2048):
        for row in batch.to_pylist():
            doc_id = _normalize_id(row["id"])
            if doc_id in metadata:
                raise ValueError(f"Duplicate metadata ID: {doc_id}")
            metadata[doc_id] = row
    statistics["metadata_documents"] = len(metadata)

    print("Scanning content, checking duplicate IDs and screening HTML...", flush=True)
    seen = {}
    candidates = {}
    for batch in pq.ParquetFile(source_paths["content"]).iter_batches(batch_size=64):
        for row in batch.to_pylist():
            statistics["content_rows"] += 1
            doc_id = _normalize_id(row["id"])
            raw_html = row["content_html"]
            if raw_html is not None and not isinstance(raw_html, str):
                raise ValueError(f"content_html must be a string or null: ID {doc_id}")
            # Distinguish a null value from an actual HTML string when deduplicating.
            digest = hashlib.sha256(
                b"null" if raw_html is None else b"html:" + raw_html.encode("utf-8")
            ).digest()
            if doc_id in seen:
                if seen[doc_id] != digest:
                    raise ValueError(f"Conflicting HTML for duplicate content ID: {doc_id}")
                statistics["identical_duplicate_rows_removed"] += 1
                continue
            seen[doc_id] = digest
            if doc_id not in metadata:
                statistics["content_without_metadata"] += 1
                continue
            statistics["shared_documents"] += 1
            group = _group_for(metadata[doc_id])
            if group is None:
                statistics["excluded_status_type_or_scope"] += 1
                continue
            result = _screen_text(raw_html or "")
            if result != "eligible":
                statistics[f"excluded_{result}"] += 1
                continue
            candidates[doc_id] = group
        if statistics["content_rows"] % 20032 == 0:
            print(f"  Scanned {statistics['content_rows']:,} content rows.", flush=True)
    statistics["unique_content_ids"] = len(seen)
    statistics["metadata_without_content"] = len(metadata.keys() - seen.keys())
    statistics["eligible_documents"] = len(candidates)
    eligible_counts = Counter(candidates.values())
    for group, quota in QUOTAS.items():
        print(f"  {group[0]}/{group[1]}: {eligible_counts[group]:,} eligible; need {quota}", flush=True)

    reused = ids_path.exists()
    if reused:
        print(f"Reusing saved IDs: {ids_path}", flush=True)
        selected = _validate_ids(_read_json(ids_path), candidates)
    else:
        selected = _validate_ids(_choose_ids(candidates, metadata, seed), candidates)

    # A second batch scan keeps the HTML of only the selected documents in memory.
    selected_set = set(selected)
    selected_html = {}
    for batch in pq.ParquetFile(source_paths["content"]).iter_batches(batch_size=64):
        for row in batch.to_pylist():
            doc_id = _normalize_id(row["id"])
            if doc_id in selected_set and doc_id not in selected_html:
                digest = hashlib.sha256(b"html:" + row["content_html"].encode("utf-8")).digest()
                if digest != seen[doc_id]:
                    raise ValueError(f"Content changed during export: ID {doc_id}")
                selected_html[doc_id] = row["content_html"]
        if len(selected_html) == len(selected):
            break
    if set(selected_html) != selected_set:
        raise ValueError("Some selected documents disappeared during export.")

    output_dir.mkdir(parents=True, exist_ok=True)
    documents_path = output_dir / "documents.jsonl"
    with tempfile.NamedTemporaryFile(dir=output_dir, suffix=".tmp", delete=False) as file:
        temporary = Path(file.name)
    documents_digest = hashlib.sha256()
    try:
        with temporary.open("wb") as file:
            for doc_id in selected:
                record = {
                    "doc_id": doc_id,
                    "content_html": selected_html[doc_id],
                    "metadata": metadata[doc_id],
                }
                line = (json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
                file.write(line)
                documents_digest.update(line)
        temporary.replace(documents_path)
    finally:
        temporary.unlink(missing_ok=True)
    if not reused:
        _atomic_json(ids_path, selected)

    manifest = {
        "repo_id": config.dataset.repo_id,
        "revision": config.dataset.revision,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_manifest": str(raw_dir / "manifest.json"),
        "selection": {
            "reused_ids": reused,
            "seed_used_for_selection": (
                previous.get("selection", {}).get("seed_used_for_selection")
                if reused else seed
            ),
            "minimum_non_whitespace_text_characters": MIN_TEXT_CHARACTERS,
            "required_status_label": "Còn hiệu lực",
            "local_selection": "round-robin over normalized pham_vi groups",
            "quality_note": "Length screening is preliminary; completeness requires review after cleaning.",
        },
        "statistics": dict(statistics),
        "groups": [
            {"type": kind, "scope": scope, "eligible": eligible_counts[(kind, scope)], "selected": quota}
            for (kind, scope), quota in QUOTAS.items()
        ],
        "selected_local_scopes": dict(Counter(
            _normalize_label(metadata[doc_id]["pham_vi"])
            for doc_id in selected if candidates[doc_id][1] == "local"
        )),
        "documents_path": str(documents_path),
        "documents_sha256": documents_digest.hexdigest(),
        "ids_path": str(ids_path),
        "selected_ids": selected,
        "sample_size": len(selected),
    }
    _atomic_json(manifest_path, manifest)
    print(f"\nSaved {len(selected)} documents: {documents_path}", flush=True)
    print(f"Saved IDs: {ids_path}\nManifest: {manifest_path}", flush=True)
    return documents_path


if __name__ == "__main__":
    from legal_rag.config import load_config

    select_sample(load_config())
