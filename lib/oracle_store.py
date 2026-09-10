"""O.R.A.C.L.E storage layer.

Every read and write of the student state goes through this module. Skills,
commands and hooks call it; nothing else touches ~/.oracle/ directly.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
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


import re
import unicodedata


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    return slug or "sem-titulo"


# --- concepts -------------------------------------------------------------

def list_concepts() -> list:
    return read_json("concepts.json", [])


def concept_level(concept: str):
    target = (concept or "").strip().lower()
    for record in list_concepts():
        if record.get("concept", "").strip().lower() == target:
            return record.get("level")
    return None


def upsert_concept(concept: str, domain: str, level: str, evidence: str) -> dict:
    """Record what the student knows.

    A concept only reaches "known" when the student demonstrated it — that
    judgement belongs to the tutor skill, which passes the evidence here.
    """
    if level not in CONCEPT_LEVELS:
        raise ValueError(f"unknown level: {level!r} (expected one of {CONCEPT_LEVELS})")

    concepts = list_concepts()
    target = (concept or "").strip().lower()
    record = {
        "concept": concept,
        "domain": domain,
        "level": level,
        "evidence": evidence,
        "updated_at": _today(),
    }

    for index, existing in enumerate(concepts):
        if existing.get("concept", "").strip().lower() == target:
            concepts[index] = record
            break
    else:
        concepts.append(record)

    write_json("concepts.json", concepts)
    return record


def known_concepts() -> list:
    return [c["concept"] for c in list_concepts() if c.get("level") == "known"]


# --- plans ----------------------------------------------------------------

def save_plan(plan: dict) -> str:
    topic = (plan or {}).get("topic")
    if not topic:
        raise ValueError("plan requires a 'topic'")

    slug = plan.get("id") or slugify(topic)
    previous = load_plan(slug) or {}

    record = {
        "id": slug,
        "topic": topic,
        "goal": plan.get("goal", ""),
        "deadline": plan.get("deadline"),
        "status": plan.get("status", "active"),
        "milestones": plan.get("milestones", []),
        "sessions": plan.get("sessions", previous.get("sessions", [])),
        "created_at": previous.get("created_at", _today()),
    }
    write_json(f"plans/{slug}.json", record)
    return slug


def load_plan(slug: str):
    return read_json(f"plans/{slug}.json", None)


def list_plans(status: str = None) -> list:
    plans_dir = home() / "plans"
    if not plans_dir.is_dir():
        return []
    plans = []
    for path in sorted(plans_dir.glob("*.json")):
        plan = read_json(f"plans/{path.name}", None)
        if plan and (status is None or plan.get("status") == status):
            plans.append(plan)
    return plans


def active_plan():
    plans = list_plans(status="active")
    return plans[0] if plans else None

# --- session state -------------------------------------------------------


def _active_path(session_id: str) -> str:
    # A session id reaches us from a hook payload; never let it walk the tree.
    raw = session_id or "unknown"
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", raw).strip("-") or "unknown"

    # Prevent collisions: if sanitization changed the ID, append a digest suffix.
    if safe != raw:
        digest = hashlib.sha256(raw.encode()).hexdigest()[:8]
        filename = f"{safe}-{digest}.json"
    else:
        filename = f"{safe}.json"

    return f".active/{filename}"


def activate(session_id: str, topic: str = "", plan_slug: str = None) -> dict:
    record = {
        "session_id": session_id,
        "topic": topic,
        "plan_slug": plan_slug,
        "started_at": _now(),
    }
    rel = _active_path(session_id)
    _write_atomic(rel, json.dumps(record, ensure_ascii=False, indent=2))
    return record


def active_record(session_id: str):
    rel = _active_path(session_id)
    path = _path(rel)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        # A broken marker means "not studying", never a crash mid-session.
        return None


def deactivate(session_id: str):
    record = active_record(session_id)
    rel = _active_path(session_id)
    path = _path(rel)
    if path.exists():
        path.unlink()
    return record


def session_log_rel(topic: str, date: str = None) -> str:
    return f"sessions/{date or _today()}-{slugify(topic)}.md"


def log_session(topic: str, text: str) -> str:
    rel = session_log_rel(topic)
    append_text(rel, text)
    return rel


def prune_active(max_age_hours: int = 24) -> int:
    """Drop markers left behind by sessions that died without SessionEnd."""
    active_dir = home() / ".active"
    if not active_dir.is_dir():
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    removed = 0
    for path in active_dir.glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            started = datetime.fromisoformat(record["started_at"])
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            stale = started < cutoff
        except (ValueError, OSError, KeyError):
            stale = True
        if stale:
            path.unlink()
            removed += 1
    return removed


# --- CLI ------------------------------------------------------------------
#
# Skills are prompts: they reach this module by shelling out. Every subcommand
# prints a single JSON object so a prompt can read the result without parsing
# prose. Exit codes: 0 ok, 2 state missing, 1 error.

def _emit(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _cmd_status(args) -> int:
    if not is_initialized():
        _emit({"initialized": False, "home": str(home())})
        return 0
    plan = active_plan()
    _emit(
        {
            "initialized": True,
            "home": str(home()),
            "storage_mode": config().get("storage_mode"),
            "concepts": len(list_concepts()),
            "known": known_concepts(),
            "profile": read_json("profile.json", {}),
            "active_plan": plan,
            "plans": len(list_plans()),
        }
    )
    return 0


def _cmd_init(args) -> int:
    _emit(init(args.mode))
    return 0


def _cmd_concepts_list(args) -> int:
    concepts = list_concepts()
    if args.level:
        concepts = [c for c in concepts if c.get("level") == args.level]
    _emit({"concepts": concepts})
    return 0


def _cmd_concepts_set(args) -> int:
    _emit(upsert_concept(args.concept, args.domain, args.level, args.evidence))
    return 0


def _cmd_profile_set(args) -> int:
    """The profile is how the tutor remembers which analogies land."""
    profile = read_json("profile.json", dict(DEFAULT_PROFILE))
    profile[args.key] = args.value
    write_json("profile.json", profile)
    _emit(profile)
    return 0


def _cmd_plan_save(args) -> int:
    raw = sys.stdin.read()
    try:
        plan = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"plano inválido no stdin: {exc}")
    slug = save_plan(plan)
    _emit({"slug": slug, "plan": load_plan(slug)})
    return 0


def _cmd_plan_show(args) -> int:
    plan = load_plan(args.slug) if args.slug else active_plan()
    _emit({"plan": plan})
    return 0


def _cmd_plan_list(args) -> int:
    _emit({"plans": list_plans(status=args.status)})
    return 0


def _cmd_session_activate(args) -> int:
    _emit(activate(args.session_id, args.topic, args.plan_slug))
    return 0


def _cmd_session_show(args) -> int:
    _emit({"active": active_record(args.session_id)})
    return 0


def _cmd_session_deactivate(args) -> int:
    _emit({"was_active": deactivate(args.session_id)})
    return 0


def _cmd_log(args) -> int:
    _emit({"path": log_session(args.topic, sys.stdin.read())})
    return 0


def _cmd_commit(args) -> int:
    _emit(commit(args.message))
    return 0


NEEDS_STATE = {
    "concepts-list", "concepts-set", "profile-set",
    "plan-save", "plan-show", "plan-list",
    "session-activate", "session-show", "session-deactivate", "log", "commit",
}


import argparse as _argparse


class _OracleArgumentParser(_argparse.ArgumentParser):
    """ArgumentParser subclass that exits with code 1 (not 2) on validation errors.

    The contract is: 0 success, 2 state not initialized, 1 other error.
    argparse.ArgumentParser.error() defaults to exit 2, which collides with our
    "state not initialized" code. This subclass redirects argument errors to exit 1.
    """

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"[oracle] {message}", file=sys.stderr)
        sys.exit(1)


def _build_parser():
    parser = _OracleArgumentParser(prog="oracle_store")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_OracleArgumentParser)

    sub.add_parser("status").set_defaults(func=_cmd_status)

    p = sub.add_parser("init")
    p.add_argument("--mode", required=True, choices=list(STORAGE_MODES))
    p.set_defaults(func=_cmd_init)

    p = sub.add_parser("concepts-list")
    p.add_argument("--level", choices=list(CONCEPT_LEVELS))
    p.set_defaults(func=_cmd_concepts_list)

    p = sub.add_parser("concepts-set")
    p.add_argument("--concept", required=True)
    p.add_argument("--domain", default="")
    p.add_argument("--level", required=True, choices=list(CONCEPT_LEVELS))
    p.add_argument("--evidence", default="")
    p.set_defaults(func=_cmd_concepts_set)

    p = sub.add_parser("profile-set")
    p.add_argument("--key", required=True)
    p.add_argument("--value", required=True)
    p.set_defaults(func=_cmd_profile_set)

    sub.add_parser("plan-save").set_defaults(func=_cmd_plan_save)

    p = sub.add_parser("plan-show")
    p.add_argument("--slug")
    p.set_defaults(func=_cmd_plan_show)

    p = sub.add_parser("plan-list")
    p.add_argument("--status")
    p.set_defaults(func=_cmd_plan_list)

    p = sub.add_parser("session-activate")
    p.add_argument("--session-id", required=True)
    p.add_argument("--topic", default="")
    p.add_argument("--plan-slug", default=None)
    p.set_defaults(func=_cmd_session_activate)

    p = sub.add_parser("session-show")
    p.add_argument("--session-id", required=True)
    p.set_defaults(func=_cmd_session_show)

    p = sub.add_parser("session-deactivate")
    p.add_argument("--session-id", required=True)
    p.set_defaults(func=_cmd_session_deactivate)

    p = sub.add_parser("log")
    p.add_argument("--topic", required=True)
    p.set_defaults(func=_cmd_log)

    p = sub.add_parser("commit")
    p.add_argument("--message", required=True)
    p.set_defaults(func=_cmd_commit)

    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command in NEEDS_STATE and not is_initialized():
        print(
            "[oracle] Estado não encontrado em "
            f"{home()}. Rode /oracle-setup primeiro.",
            file=sys.stderr,
        )
        return 2
    try:
        return args.func(args)
    except (ValueError, OracleNotInitialized) as exc:
        print(f"[oracle] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
