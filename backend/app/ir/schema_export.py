from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Type

from pydantic import BaseModel

from app.ir.deck_ir import DeckIR
from app.ir.document_ir import DocumentIR
from app.ir.word_ir import WordIR


SCHEMA_MODELS: dict[str, Type[BaseModel]] = {
    "word_ir": WordIR,
    "document_ir": DocumentIR,
    "deck_ir": DeckIR,
}

SCHEMA_HISTORY_FILENAME = "schema_history.json"


class SchemaSnapshotError(RuntimeError):
    """Raised when checked-in schemas do not match the contract models."""


class SchemaVersionError(SchemaSnapshotError):
    """Raised when a schema changes without a new ir_version."""


def normalized_schema(model: Type[BaseModel]) -> dict:
    encoded = json.dumps(model.model_json_schema(), ensure_ascii=False, sort_keys=True)
    return json.loads(encoded)


def canonical_schema_hash(schema: dict) -> str:
    payload = json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(payload).hexdigest()


def schema_without_descriptions(value):
    if isinstance(value, dict):
        return {
            key: schema_without_descriptions(item)
            for key, item in value.items()
            if key != "description"
        }
    if isinstance(value, list):
        return [schema_without_descriptions(item) for item in value]
    return value


def _is_description_only_update(path: Path, schema: dict) -> bool:
    if not path.exists():
        return False
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return schema_without_descriptions(current) == schema_without_descriptions(schema)


def schema_version(schema: dict) -> str:
    version = schema.get("properties", {}).get("ir_version", {}).get("const")
    if not isinstance(version, str) or not version:
        raise SchemaSnapshotError("schema must expose properties.ir_version.const")
    return version


def _load_history(output_dir: Path) -> dict:
    path = output_dir / SCHEMA_HISTORY_FILENAME
    if not path.exists():
        raise SchemaSnapshotError(f"schema history is missing: {path}")
    try:
        history = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SchemaSnapshotError(f"schema history is unreadable: {path}: {exc}") from exc
    if history.get("schema_format") != 1 or not isinstance(history.get("schemas"), dict):
        raise SchemaSnapshotError(f"schema history has an unsupported structure: {path}")
    return history


def verify_schema_snapshots(output_dir: Path) -> list[Path]:
    history = _load_history(output_dir)
    verified: list[Path] = []
    for name, model in SCHEMA_MODELS.items():
        expected = normalized_schema(model)
        version = schema_version(expected)
        digest = canonical_schema_hash(expected)
        recorded = history["schemas"].get(name, {}).get(version)
        if recorded != digest:
            raise SchemaVersionError(
                f"{name} version {version} is not registered with its current schema hash; "
                "bump ir_version and run scripts/export_schemas.py"
            )
        path = output_dir / f"{name}.schema.json"
        if not path.exists():
            raise SchemaSnapshotError(f"schema snapshot is missing: {path}")
        try:
            actual = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SchemaSnapshotError(f"schema snapshot is unreadable: {path}: {exc}") from exc
        if actual != expected:
            raise SchemaSnapshotError(
                f"schema snapshot drifted: {path}; run scripts/export_schemas.py only after an ir_version bump"
            )
        verified.append(path)
    return verified


def export_schemas(output_dir: Path, *, update_history: bool = False) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    history = _load_history(output_dir)
    pending: list[tuple[str, Path, dict, str, str]] = []
    for name, model in SCHEMA_MODELS.items():
        schema = normalized_schema(model)
        version = schema_version(schema)
        digest = canonical_schema_hash(schema)
        recorded = history["schemas"].get(name, {}).get(version)
        path = output_dir / f"{name}.schema.json"
        if recorded is not None and recorded != digest:
            if not update_history or not _is_description_only_update(path, schema):
                raise SchemaVersionError(f"{name} schema changed while ir_version stayed at {version}")
        if recorded is None and not update_history:
            raise SchemaVersionError(
                f"{name} version {version} is new; rerun explicit export with update_history=True"
            )
        pending.append((name, path, schema, version, digest))

    written: list[Path] = []
    for name, path, schema, version, digest in pending:
        if update_history:
            history["schemas"].setdefault(name, {})[version] = digest
        path.write_text(
            json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    if update_history:
        history_path = output_dir / SCHEMA_HISTORY_FILENAME
        history_path.write_text(
            json.dumps(history, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(history_path)
    return written
