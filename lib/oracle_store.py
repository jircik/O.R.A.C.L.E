"""O.R.A.C.L.E storage layer.

Every read and write of the student state goes through this module. Skills,
commands and hooks call it; nothing else touches ~/.oracle/ directly.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

STORAGE_MODES = ("plain", "git", "git-remote")
CONCEPT_LEVELS = ("known", "shaky", "gap")

DEFAULT_PROFILE = {
    "goals": [],
    "explanation_style": "",
    "notes": "",
}


class OracleNotInitialized(Exception):
    """Raised when the student state does not exist yet."""


def home() -> Path:
    return Path(os.environ.get("ORACLE_HOME", str(Path.home() / ".oracle")))


def is_initialized() -> bool:
    return (home() / "config.json").exists()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init(mode: str) -> dict:
    """Create the storage layout, or update the mode of an existing one.

    Never destroys existing data: re-running only rewrites config.json.
    """
    if mode not in STORAGE_MODES:
        raise ValueError(f"unknown storage mode: {mode!r} (expected one of {STORAGE_MODES})")

    root = home()
    root.mkdir(parents=True, exist_ok=True)
    (root / "plans").mkdir(exist_ok=True)
    (root / "sessions").mkdir(exist_ok=True)
    (root / ".active").mkdir(exist_ok=True)

    existing = {}
    if (root / "config.json").exists():
        existing = read_json("config.json", {})

    cfg = {
        "storage_mode": mode,
        "version": 1,
        "created_at": existing.get("created_at", _now()),
    }
    write_json("config.json", cfg)

    if not (root / "profile.json").exists():
        write_json("profile.json", dict(DEFAULT_PROFILE))
    if not (root / "concepts.json").exists():
        write_json("concepts.json", [])

    return cfg


def config() -> dict:
    if not is_initialized():
        raise OracleNotInitialized(
            "~/.oracle não existe. Rode /oracle-setup antes de usar o O.R.A.C.L.E."
        )
    return read_json("config.json", {})


def _path(rel: str) -> Path:
    return home() / rel


def read_json(rel: str, default):
    """Read JSON. A corrupt file is backed up and the default returned."""
    path = _path(rel)
    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        backup = path.with_suffix(path.suffix + ".bak")
        backup.write_text(raw, encoding="utf-8")
        print(
            f"[oracle] {rel} está corrompido. Backup salvo em {backup.name}; "
            "seguindo com o valor padrão.",
            file=sys.stderr,
        )
        return default


def write_json(rel: str, data) -> None:
    _write_atomic(rel, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def read_text(rel: str, default: str = "") -> str:
    path = _path(rel)
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def append_text(rel: str, text: str) -> None:
    _write_atomic(rel, read_text(rel) + text)


def _write_atomic(rel: str, content: str) -> None:
    path = _path(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".tmp-{path.name}"
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)
