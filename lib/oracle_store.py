"""O.R.A.C.L.E storage layer.

Every read and write of the student state goes through this module. Skills,
commands and hooks call it; nothing else touches ~/.oracle/ directly.
"""

import json
import os
import shutil
import subprocess
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

    if mode in ("git", "git-remote") and git_available():
        _ensure_repo()

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


def git_available() -> bool:
    return shutil.which("git") is not None


def _git(*args, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(home()),
        capture_output=True,
        text=True,
        check=check,
    )


def _ensure_repo() -> None:
    if (home() / ".git").is_dir():
        return
    _git("init", "-q")
    # A study log is personal; make that explicit for anyone who pushes it.
    gitignore = home() / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(".active/\n*.bak\n", encoding="utf-8")


def _has_remote() -> bool:
    return bool(_git("remote").stdout.strip())


def commit(message: str) -> dict:
    """Persist the current state according to the configured storage mode.

    plain      -> no-op
    git        -> local commit
    git-remote -> local commit, then push (a failed push never loses data)
    """
    mode = config().get("storage_mode", "plain")
    result = {"mode": mode, "committed": False, "pushed": False, "warning": None}

    if mode == "plain":
        return result

    if not git_available():
        result["warning"] = (
            "git não está instalado; o estado foi salvo em disco mas não versionado."
        )
        return result

    _ensure_repo()
    _git("add", "-A")

    if not _git("status", "--porcelain").stdout.strip():
        return result

    committed = _git("commit", "-q", "-m", message)
    if committed.returncode != 0:
        result["warning"] = f"git commit falhou: {committed.stderr.strip()}"
        return result
    result["committed"] = True

    if mode != "git-remote":
        return result

    if not _has_remote():
        result["warning"] = (
            "Nenhum remoto configurado. O commit local foi feito; rode /oracle-setup "
            "para apontar um repositório remoto."
        )
        return result

    branch = _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "main"
    pushed = _git("push", "-q", "-u", "origin", branch)
    if pushed.returncode == 0:
        result["pushed"] = True
    else:
        result["warning"] = (
            "Não consegui dar push (offline ou sem acesso). O commit local está "
            f"salvo e sobe no próximo sync. Detalhe: {pushed.stderr.strip()[:200]}"
        )
    return result
