#!/usr/bin/env python3
"""SessionEnd hook: persist the tutoring session and close it.

This is a backstop, not the only write point. The tutor records concepts as
the student demonstrates them, during the session — an interrupted session
must never discard demonstrated progress.

/oracle-off calls save_and_close() directly, and the function is idempotent,
so turning the mode off by hand and then closing the terminal logs once.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

import oracle_store as store


def save_and_close(session_id: str) -> dict:
    record = store.active_record(session_id)
    if not record:
        return {"saved": False, "log": None, "commit": None}

    topic = record.get("topic") or "sessão livre"
    entry = (
        f"\n## {store._today()} — {topic}\n"
        f"- iniciada: {record.get('started_at')}\n"
        f"- plano: {record.get('plan_slug') or '(nenhum)'}\n"
    )
    log_rel = store.log_session(topic, entry)

    # Close the marker immediately after logging, before plan-link operations.
    # If plan-link fails, we lose a cross-reference (cosmetic) rather than
    # duplicate the session log (not recoverable without hand-editing).
    store.deactivate(session_id)

    # A failure here (bad plan file, disk issue, ...) must never skip the
    # commit below: losing the plan cross-reference is cosmetic, but on the
    # git/git-remote tracks skipping commit() means the session is logged to
    # disk but never versioned, with no warning to the student.
    plan_slug = record.get("plan_slug")
    if plan_slug:
        try:
            plan = store.load_plan(plan_slug)
            if plan:
                log_stem = Path(log_rel).stem
                if log_stem not in plan.get("sessions", []):
                    plan.setdefault("sessions", []).append(log_stem)
                    store.save_plan(plan)
        except Exception as exc:
            print(f"[oracle] falha ao vincular a sessão ao plano: {exc}", file=sys.stderr)

    result = store.commit(f"oracle: sessão de estudo sobre {topic}")
    return {"saved": True, "log": log_rel, "commit": result}


def main() -> int:
    argv = sys.argv[1:]

    if "--off" in argv:
        session_id = None
        if "--session-id" in argv:
            session_id = argv[argv.index("--session-id") + 1]
        session_id = session_id or os.environ.get("CLAUDE_CODE_SESSION_ID")
        if not session_id or not store.is_initialized():
            print(json.dumps({"saved": False, "log": None, "commit": None}))
            return 0
        print(json.dumps(save_and_close(session_id), ensure_ascii=False, indent=2))
        return 0

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, OSError):
        return 0

    if not store.is_initialized():
        return 0

    session_id = payload.get("session_id")
    if session_id:
        save_and_close(session_id)

    store.prune_active()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
