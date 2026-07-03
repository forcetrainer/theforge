#!/usr/bin/env python3
"""review-packet.py: extract a plan's Task N block plus its git diff into a
self-contained review packet for a reviewer.

Usage:
    review-packet.py <plan.md> <task-number> --base <git-ref> [--out <dir>]

Never emits a silently thin packet: any failure to locate the task block or
to run git exits nonzero with a message on stderr.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile


def extract_task_block(text, task_number):
    """Return the ``### Task <task_number>:`` block (through the next
    ``##``/``###`` heading or EOF), or None if the task isn't found."""
    lines = text.splitlines(keepends=True)
    start_pattern = re.compile(r"^###\s+Task\s+" + re.escape(str(task_number)) + r":")
    start_idx = None
    for i, line in enumerate(lines):
        if start_pattern.match(line):
            start_idx = i
            break
    if start_idx is None:
        return None

    end_pattern = re.compile(r"^#{2,3}\s")
    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        if end_pattern.match(lines[i]):
            end_idx = i
            break
    return "".join(lines[start_idx:end_idx])


def build_packet(task_block, base, diff_output):
    if diff_output.strip() == "":
        diff_body = "no changes vs {}\n".format(base)
    else:
        diff_body = diff_output
        if not diff_body.endswith("\n"):
            diff_body += "\n"
    # Fence must outrun any backtick run in the diff so a diffed line like
    # " ```" (context-prefixed fence, ≤3-space indent) can't close it early.
    longest_run = max(
        (len(m.group(0)) for m in re.finditer(r"`+", diff_body)), default=0
    )
    fence = "`" * max(3, longest_run + 1)
    diff_section = fence + "diff\n" + diff_body + fence + "\n"
    return task_block.rstrip("\n") + "\n\n" + diff_section


def main(argv=None):
    parser = argparse.ArgumentParser(prog="review-packet.py")
    parser.add_argument("plan")
    parser.add_argument("task_number", type=int)
    parser.add_argument("--base", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    try:
        with open(args.plan, "r", encoding="utf-8") as f:
            plan_text = f.read()
    except OSError as e:
        print("error: cannot read plan file {}: {}".format(args.plan, e), file=sys.stderr)
        return 1

    task_block = extract_task_block(plan_text, args.task_number)
    if task_block is None:
        print(
            "error: Task {} not found in {}".format(args.task_number, args.plan),
            file=sys.stderr,
        )
        return 1

    plan_dir = os.path.dirname(os.path.abspath(args.plan)) or "."

    try:
        result = subprocess.run(
            ["git", "diff", args.base],
            cwd=plan_dir,
            capture_output=True,
            text=True,
        )
    except OSError as e:
        print("error: failed to invoke git: {}".format(e), file=sys.stderr)
        return 1

    if result.returncode != 0:
        print(
            "error: git diff {} failed in {}:".format(args.base, plan_dir),
            file=sys.stderr,
        )
        print(result.stderr, end="", file=sys.stderr)
        return 1

    packet = build_packet(task_block, args.base, result.stdout)

    out_dir = args.out if args.out else tempfile.mkdtemp()
    try:
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "task-{}-review.md".format(args.task_number))
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(packet)
    except OSError as e:
        print("error: cannot write output to {}: {}".format(out_dir, e), file=sys.stderr)
        return 1

    print(os.path.abspath(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
