#!/usr/bin/env python3
"""forge-run.py — deterministic whole-plan task runner over ``codex exec``.

Task 2 scope: the sequential task loop (dependency order), worker dispatch via
one ``codex exec`` process per task, direct acceptance-command execution, JSON
receipts, a ``run.json`` summary, and plan-checkbox ledger annotations. Review
dispatch, the rework cap, halt/resume, and final review are added in Task 3.

Usage:
    forge-run.py <plan.md> --spec <spec.md> [--run-dir DIR] [--codex-bin PATH]

Exit codes:
    0  every task passed
    1  contract/usage error (malformed plan, brief-generation failure)
    2  halted on an escalated task

Reuses ``extract-brief.py`` for all plan/spec parsing — no duplicated heading
grammar. Tier -> model/effort mapping lives in exactly one table (``TIER_MAP``).
All parse failures raise loudly naming the cause (DECISIONS 2026-07-11);
``ultra`` reasoning effort is never emitted (DECISIONS 2026-07-13).
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field


SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPTS_DIR)

# Reuse extract-brief.py (hyphenated filename -> importlib) for plan/spec parsing.
_eb_spec = importlib.util.spec_from_file_location(
    "forge_run_extract_brief", os.path.join(SCRIPTS_DIR, "extract-brief.py")
)
eb = importlib.util.module_from_spec(_eb_spec)
_eb_spec.loader.exec_module(eb)


# Tier -> (model, model_reasoning_effort). Single update point on model churn.
TIER_MAP = {
    "trivial": ("gpt-5.6-luna", "medium"),
    "standard": ("gpt-5.6-terra", "high"),
    "complex": ("gpt-5.6-sol", "high"),
}
# Reviewer routing (used in Task 3); trivial tier has no reviewer.
REVIEW_MAP = {
    "standard": ("gpt-5.6-terra", "high"),
    "complex": ("gpt-5.6-sol", "high"),
}
# Worker contract source per tier — agents/*.md body (frontmatter stripped),
# single source shared with the Claude Code harness.
CONTRACT_AGENT = {
    "trivial": "forge-light",
    "standard": "forge-standard",
    "complex": "forge-deep",
}

_ACC_TAIL_CHARS = 2000


@dataclass
class Task:
    number: int
    title: str
    tier: str
    depends_on: list = field(default_factory=list)
    acceptance_commands: list = field(default_factory=list)
    checkbox_line: int = -1


@dataclass
class AcceptanceResult:
    command: str
    exit_code: int
    output_tail: str


@dataclass
class WorkerResult:
    exit_code: int
    last_message: str
    argv: list


@dataclass
class TaskOutcome:
    status: str  # "passed" | "escalated"
    attempts: int
    summary: str


# --- plan parsing (reuses extract-brief heading grammar) --------------------


def _field_value(block_lines, block_mask, name):
    """First-line value of a single-line ``**Name:**`` field, or None."""
    prefix = "**{}:**".format(name)
    for i, ln in enumerate(block_lines):
        if not block_mask[i] and ln.startswith(prefix):
            return ln[len(prefix):].strip()
    return None


def _field_text(block_lines, block_mask, name):
    """Full text of a ``**Name:**`` field: its line plus any wrapped
    continuation, joined with spaces. A blank line, a new field, a heading, or a
    fence ends it."""
    prefix = "**{}:**".format(name)
    for i, ln in enumerate(block_lines):
        if block_mask[i] or not ln.startswith(prefix):
            continue
        parts = [ln[len(prefix):]]
        j = i + 1
        while j < len(block_lines):
            if block_mask[j]:
                break
            nxt = block_lines[j]
            if (
                nxt.strip() == ""
                or eb.FIELD_LINE_RE.match(nxt)
                or re.match(r"^#{1,6}\s", nxt)
            ):
                break
            parts.append(nxt)
            j += 1
        return " ".join(p.strip() for p in parts).strip()
    return ""


def _parse_commands(text):
    """Inline-code spans on an ``**Acceptance:**`` line are the commands."""
    return [
        m.group(1).strip()
        for m in re.finditer(r"`([^`]+)`", text)
        if m.group(1).strip()
    ]


def _parse_depends(text):
    return [int(n) for n in re.findall(r"Task\s+(\d+)", text)]


def parse_plan_tasks(plan_path):
    """Parse every ``### Task N:`` block into a Task. Raises RuntimeError naming
    the cause on a wrong-level task heading or a duplicate task number — never
    guesses (DECISIONS 2026-07-11)."""
    lines = eb.read_lines(plan_path)
    mask = eb.fence_mask(lines)

    starts = []  # (number, line_index)
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        m = eb.TASK_HEADING_RE.match(line)
        if m:
            starts.append((int(m.group(1)), i))
            continue
        wl = eb.ANY_LEVEL_TASK_HEADING_RE.match(line)
        if wl and len(wl.group(1)) != 3:
            raise RuntimeError(
                "task {n} heading must be '### Task {n}:' (three #), found "
                "'{lvl} Task {n}:' at line {ln} in {p}".format(
                    n=int(wl.group(2)), lvl=wl.group(1), ln=i + 1, p=plan_path
                )
            )
    if not starts:
        raise RuntimeError("no '### Task N:' headings found in {}".format(plan_path))

    nums = [n for n, _ in starts]
    dups = sorted({n for n in nums if nums.count(n) > 1})
    if dups:
        raise RuntimeError(
            "duplicate task number(s) {} — '### Task N:' headings must be unique "
            "in {}".format(", ".join(str(d) for d in dups), plan_path)
        )

    tasks = []
    for num, start in starts:
        block = eb.extract_task_block(lines, num)
        heading = lines[start]
        tm = re.match(r"^###\s+Task\s+\d+:\s*(.*)$", heading)
        title = tm.group(1).strip() if tm else ""

        block_lines = block.splitlines()
        block_mask = eb.fence_mask(block_lines)

        tier = _field_value(block_lines, block_mask, "Tier")
        if tier is None:
            raise RuntimeError("task {} is missing the **Tier:** line".format(num))
        tier = tier.strip().lower()
        if tier not in TIER_MAP:
            raise RuntimeError(
                "task {} has unknown tier {!r} — expected one of {}".format(
                    num, tier, ", ".join(sorted(TIER_MAP))
                )
            )

        depends_on = _parse_depends(_field_value(block_lines, block_mask, "Depends on") or "")
        acceptance = _parse_commands(_field_text(block_lines, block_mask, "Acceptance"))

        checkbox_line = -1
        for offset, bl in enumerate(block_lines):
            if block_mask[offset]:
                continue
            if re.match(r"^\s*[-*]\s*\[[ xX]\]", bl):
                checkbox_line = start + offset
                break

        tasks.append(
            Task(
                number=num,
                title=title,
                tier=tier,
                depends_on=depends_on,
                acceptance_commands=acceptance,
                checkbox_line=checkbox_line,
            )
        )
    return tasks


def order_tasks(tasks):
    """Return tasks in dependency order (each dependency before its dependents).
    Raises on an unknown dependency or a cycle."""
    by_num = {t.number: t for t in tasks}
    for t in tasks:
        for d in t.depends_on:
            if d not in by_num:
                raise RuntimeError(
                    "task {} depends on unknown task {}".format(t.number, d)
                )
    order = []
    state = {}  # number -> 0 visiting, 1 done

    def visit(n):
        s = state.get(n)
        if s == 1:
            return
        if s == 0:
            raise RuntimeError("dependency cycle involving task {}".format(n))
        state[n] = 0
        for d in by_num[n].depends_on:
            visit(d)
        state[n] = 1
        order.append(by_num[n])

    for t in tasks:
        visit(t.number)
    return order


# --- worker dispatch --------------------------------------------------------


def _agents_dir():
    return os.environ.get("FORGE_AGENTS_DIR") or os.path.join(REPO_ROOT, "agents")


def contract_preamble(tier):
    """Worker-contract text: agents/<tier-agent>.md body with YAML frontmatter
    stripped. Missing source raises (a worker with no contract is a silent
    degradation)."""
    agent = CONTRACT_AGENT[tier]
    path = os.path.join(_agents_dir(), agent + ".md")
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise RuntimeError("worker contract source missing: {}: {}".format(path, e))
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()


def dispatch_worker(task, brief_path, codex_bin, run_dir):
    """One ``codex exec`` worker process, tier-pinned model/effort. Prompt =
    contract preamble + brief. Returns the exit code, last message, and the
    exact argv emitted."""
    model, effort = TIER_MAP[task.tier]
    preamble = contract_preamble(task.tier)
    with open(brief_path, "r", encoding="utf-8") as f:
        brief = f.read()
    prompt = preamble + "\n\n" + brief
    last_msg_path = os.path.join(run_dir, "task-{}-worker-last.txt".format(task.number))
    argv = [
        codex_bin,
        "exec",
        "-m",
        model,
        "-c",
        "model_reasoning_effort={}".format(effort),
        "--output-last-message",
        last_msg_path,
        prompt,
    ]
    proc = subprocess.run(argv, capture_output=True, text=True)
    last_message = ""
    if os.path.exists(last_msg_path):
        with open(last_msg_path, "r", encoding="utf-8") as f:
            last_message = f.read()
    return WorkerResult(exit_code=proc.returncode, last_message=last_message, argv=argv)


def run_acceptance(task, cwd):
    """Run each acceptance command directly (shell) in ``cwd``; capture exit code
    and an output tail."""
    results = []
    for cmd in task.acceptance_commands:
        proc = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
        combined = (proc.stdout or "") + (proc.stderr or "")
        results.append(
            AcceptanceResult(
                command=cmd,
                exit_code=proc.returncode,
                output_tail=combined[-_ACC_TAIL_CHARS:],
            )
        )
    return results


# --- receipts & ledger ------------------------------------------------------


def write_receipt(run_dir, task, attempt, receipt_dict):
    os.makedirs(run_dir, exist_ok=True)
    path = os.path.join(run_dir, "task-{}-attempt-{}.json".format(task.number, attempt))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(receipt_dict, f, indent=2)
    return path


def write_run_json(run_dir, plan_path, spec_path, status, task_summaries):
    os.makedirs(run_dir, exist_ok=True)
    data = {
        "plan": os.path.abspath(plan_path),
        "spec": os.path.abspath(spec_path),
        "status": status,
        "tasks": task_summaries,
    }
    path = os.path.join(run_dir, "run.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def annotate_ledger(plan_path, task, status_line):
    """Check the task's plan checkbox and append ``— <status_line>``. Idempotent:
    replaces any prior annotation."""
    if task.checkbox_line < 0:
        return
    with open(plan_path, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.splitlines(keepends=True)
    raw = lines[task.checkbox_line]
    nl = "\n" if raw.endswith("\n") else ""
    body = raw[: len(raw) - len(nl)] if nl else raw
    body = re.sub(r"\[[ xX]\]", "[x]", body, count=1)
    body = re.sub(r"\s+—\s.*$", "", body)
    lines[task.checkbox_line] = body + " — " + status_line + nl
    with open(plan_path, "w", encoding="utf-8") as f:
        f.write("".join(lines))


# --- per-task execution & plan loop -----------------------------------------


def _brief_for(task, plan_path, spec_path, run_dir):
    brief = eb.build_brief(plan_path, task.number, spec_path)
    brief_path = os.path.join(run_dir, "task-{}-brief.md".format(task.number))
    with open(brief_path, "w", encoding="utf-8") as f:
        f.write(brief)
    sha = hashlib.sha256(brief.encode("utf-8")).hexdigest()
    return brief_path, sha


def execute_task(task, plan_path, spec_path, run_dir, codex_bin, cwd):
    """Task 2: a single worker attempt plus acceptance. Passes when the worker
    exits 0 and every acceptance command exits 0; otherwise escalates (the rework
    loop and review arrive in Task 3)."""
    attempt = 1
    model, effort = TIER_MAP[task.tier]
    brief_path, brief_sha = _brief_for(task, plan_path, spec_path, run_dir)

    worker = dispatch_worker(task, brief_path, codex_bin, run_dir)
    acceptance = run_acceptance(task, cwd)

    worker_ok = worker.exit_code == 0
    acc_ok = all(r.exit_code == 0 for r in acceptance)
    passed = worker_ok and acc_ok

    if passed:
        status = "passed"
        summary = ""
    else:
        status = "escalated"
        if not worker_ok:
            summary = "worker exited {}".format(worker.exit_code)
        else:
            failed = next(r for r in acceptance if r.exit_code != 0)
            summary = "acceptance failed: {}".format(failed.command)

    receipt = {
        "task_number": task.number,
        "title": task.title,
        "tier": task.tier,
        "model": model,
        "effort": effort,
        "brief_path": os.path.abspath(brief_path),
        "brief_sha256": brief_sha,
        "worker_exit_code": worker.exit_code,
        "acceptance_results": [asdict(r) for r in acceptance],
        "review_verdict": None,
        "attempt": attempt,
        "status": status,
    }
    write_receipt(run_dir, task, attempt, receipt)
    return TaskOutcome(status=status, attempts=attempt, summary=summary)


def run_plan(plan_path, spec_path, run_dir, codex_bin, cwd):
    os.makedirs(run_dir, exist_ok=True)
    tasks = parse_plan_tasks(plan_path)
    order = order_tasks(tasks)

    task_summaries = []
    overall = "passed"

    # order_tasks yields dependency order (each dependency before its dependents)
    # and the loop breaks on the first escalation, so a dependent is never reached
    # unless every dependency already passed — no separate depends-on guard needed.
    for task in order:
        outcome = execute_task(task, plan_path, spec_path, run_dir, codex_bin, cwd)
        task_summaries.append(
            {
                "number": task.number,
                "title": task.title,
                "tier": task.tier,
                "status": outcome.status,
                "attempts": outcome.attempts,
            }
        )
        if outcome.status == "passed":
            annotate_ledger(
                plan_path, task, "passed, {} attempt(s)".format(outcome.attempts)
            )
        else:
            annotate_ledger(plan_path, task, "escalated: {}".format(outcome.summary))
            overall = "escalated"
            break

    write_run_json(run_dir, plan_path, spec_path, overall, task_summaries)
    return 0 if overall == "passed" else 2


def _default_run_dir():
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    return os.path.join(".forge", "runs", stamp)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="forge-run.py",
        description="Deterministic whole-plan task runner over `codex exec`.",
    )
    parser.add_argument("plan", help="approved plan markdown file")
    parser.add_argument("--spec", required=True, help="design spec markdown file")
    parser.add_argument(
        "--run-dir",
        default=None,
        help="receipt directory (default: .forge/runs/<timestamp>/)",
    )
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="path to the codex executable (test seam; default: codex on PATH)",
    )
    args = parser.parse_args(argv)

    run_dir = args.run_dir or _default_run_dir()
    try:
        return run_plan(args.plan, args.spec, run_dir, args.codex_bin, os.getcwd())
    except RuntimeError as e:
        print("error: {}".format(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
