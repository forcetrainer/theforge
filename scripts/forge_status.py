"""forge_status — run-state reader and renderers for session awareness.

Reads a run dir (`run.json` + per-task receipts) into a plain state dict and
renders it two ways: the `forge-run.py --status` multi-line summary and the
compact `UserPromptSubmit` hook block. Pure file reads — no dispatch, no git,
no subprocess — so both the runner and the hook can share it.
"""
import json
import os
import re

_ATTEMPT_RE = re.compile(r"^task-(\d+)-attempt-(\d+)\.json$")
_FINDING_MAX = 100

# run.json top-level status -> external state vocabulary.
_STATE_MAP = {
    "running": "running",
    "passed": "completed",
    "escalated": "halted",
    "escalated-final-review": "halted",
    "contract-error": "contract-error",
}


def _load_run_json(run_dir):
    try:
        with open(os.path.join(run_dir, "run.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _latest_receipts(run_dir):
    """Map task number -> highest-attempt receipt dict."""
    best = {}  # number -> (attempt, dict)
    for name in os.listdir(run_dir):
        m = _ATTEMPT_RE.match(name)
        if not m:
            continue
        number, attempt = int(m.group(1)), int(m.group(2))
        if number in best and best[number][0] >= attempt:
            continue
        try:
            with open(os.path.join(run_dir, name), "r", encoding="utf-8") as f:
                best[number] = (attempt, json.load(f))
        except (OSError, ValueError):
            continue
    return {n: d for n, (a, d) in best.items()}


def _latest_mtime(run_dir):
    newest = 0.0
    for name in os.listdir(run_dir):
        if name.endswith(".json"):
            try:
                newest = max(newest, os.path.getmtime(os.path.join(run_dir, name)))
            except OSError:
                pass
    return newest


def _truncate(text):
    text = text.strip().replace("\n", " ")
    return text if len(text) <= _FINDING_MAX else text[:_FINDING_MAX] + "…"


def read_run_state(run_dir):
    """Parse ``run.json`` + latest receipts into a state dict, or None when the
    dir is absent or holds neither. See module docstring for the shape."""
    if not os.path.isdir(run_dir):
        return None
    run = _load_run_json(run_dir)
    receipts = _latest_receipts(run_dir)
    if run is None and not receipts:
        return None

    raw_status = run.get("status") if run else None
    state = _STATE_MAP.get(raw_status, "running") if run else "running"

    # Per-task list: prefer run.json summaries, fall back to receipts.
    if run and run.get("tasks"):
        summaries = run["tasks"]
    else:
        summaries = [
            {"number": n, "status": r.get("status"), "attempts": r.get("attempt", 1)}
            for n, r in sorted(receipts.items())
        ]

    tasks = []
    for s in sorted(summaries, key=lambda x: x.get("number", 0)):
        number = s.get("number")
        finding = None
        if s.get("status") == "escalated":
            r = receipts.get(number)
            outstanding = (r or {}).get("outstanding_findings") or []
            if outstanding:
                finding = _truncate(outstanding[0])
        tasks.append(
            {
                "number": number,
                "status": s.get("status"),
                "attempts": s.get("attempts", 1),
                "finding": finding,
            }
        )

    reason = None
    if state == "contract-error":
        reason = (run or {}).get("contract_error") or "contract error"
    elif state == "halted":
        if raw_status == "escalated-final-review":
            reason = "final review escalated"
        else:
            first = next((t for t in tasks if t["status"] == "escalated"), None)
            reason = "task {} escalated".format(first["number"]) if first else "escalated"

    return {
        "run_dir": run_dir,
        "state": state,
        "reason": reason,
        "latest_mtime": _latest_mtime(run_dir),
        "tasks": tasks,
    }


def render_status(state):
    """Multi-line ``--status`` output: header line + one line per task."""
    header = "run {}: {}".format(state["run_dir"], state["state"].upper())
    if state["reason"] and state["state"] in ("halted", "contract-error"):
        header += " — " + state["reason"]
    lines = [header]
    for t in state["tasks"]:
        line = "task {}: {}, attempts {}".format(t["number"], t["status"], t["attempts"])
        if t["finding"]:
            line += " — " + t["finding"]
        lines.append(line)
    return "\n".join(lines)


def _compress_tasks(tasks):
    """Range-compress consecutive same-status tasks: ``tasks 1-4: passed``."""
    lines = []
    i = 0
    while i < len(tasks):
        j = i
        while (
            j + 1 < len(tasks)
            and tasks[j + 1]["status"] == tasks[i]["status"]
            and tasks[j + 1]["number"] == tasks[j]["number"] + 1
        ):
            j += 1
        a, b, status = tasks[i]["number"], tasks[j]["number"], tasks[i]["status"]
        lines.append(
            "task {}: {}".format(a, status) if a == b
            else "tasks {}-{}: {}".format(a, b, status)
        )
        i = j + 1
    return lines


def render_hook_block(state, now, max_lines=6, age_cutoff_h=12):
    """Compact ≤ ``max_lines`` block for the UserPromptSubmit hook, or None when
    the run is terminal and older than ``age_cutoff_h`` hours."""
    if state["state"] != "running" and now - state["latest_mtime"] > age_cutoff_h * 3600:
        return None
    head = "state: " + state["state"].upper()
    if state["reason"]:
        head += " — " + state["reason"]
    lines = ["run {}".format(os.path.basename(state["run_dir"].rstrip("/"))), head]
    lines.extend(_compress_tasks(state["tasks"]))
    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + ["…"]
    return "\n".join(lines)
