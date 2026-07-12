import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "review-packet.py")

PLAN_TASK1 = """# Fixture Plan

**Goal:** Do the thing.

### Task 1: First task
- [ ] Done

**Files:**
- Modify: `foo.txt`

**Acceptance:** `true`

**Tier:** trivial

**Depends on:** nothing

### Task 2: Second task
- [ ] Done

**Files:**
- Modify: `bar.txt`
"""


def run_script(args):
    return subprocess.run(
        [sys.executable, SCRIPT] + args,
        capture_output=True,
        text=True,
    )


class ReviewPacketGitFixtureTests(unittest.TestCase):
    def setUp(self):
        self.repo_dir = tempfile.mkdtemp(prefix="review-packet-repo-")
        self.addCleanup(shutil.rmtree, self.repo_dir, ignore_errors=True)
        self._git("init")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "Test")

        self.plan_path = os.path.join(self.repo_dir, "plan.md")
        with open(self.plan_path, "w") as f:
            f.write(PLAN_TASK1)

        self.src_path = os.path.join(self.repo_dir, "src.txt")
        with open(self.src_path, "w") as f:
            f.write("line one\n")

        self._git("add", ".")
        self._git("commit", "-m", "initial commit")
        self.commit1 = self._git_output("rev-parse", "HEAD").strip()

        with open(self.src_path, "a") as f:
            f.write("line two\n")
        self._git("add", ".")
        self._git("commit", "-m", "second commit")
        self.commit2 = self._git_output("rev-parse", "HEAD").strip()

    def _git(self, *args):
        subprocess.run(
            ["git"] + list(args),
            cwd=self.repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )

    def _git_output(self, *args):
        result = subprocess.run(
            ["git"] + list(args),
            cwd=self.repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout

    def test_packet_contains_task_block_and_diff(self):
        out_dir = tempfile.mkdtemp(prefix="review-packet-out-")
        self.addCleanup(shutil.rmtree, out_dir, ignore_errors=True)
        result = run_script(
            [self.plan_path, "1", "--base", self.commit1, "--out", out_dir]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        out_path = result.stdout.strip()
        self.assertTrue(os.path.isfile(out_path))
        with open(out_path) as f:
            content = f.read()
        self.assertIn("### Task 1: First task", content)
        self.assertNotIn("### Task 2:", content)
        self.assertIn("line two", content)
        self.assertIn("```diff", content)

    def test_clean_base_head_yields_empty_diff_notice(self):
        out_dir = tempfile.mkdtemp(prefix="review-packet-out-")
        self.addCleanup(shutil.rmtree, out_dir, ignore_errors=True)
        result = run_script([self.plan_path, "1", "--base", "HEAD", "--out", out_dir])
        self.assertEqual(result.returncode, 0, result.stderr)
        out_path = result.stdout.strip()
        with open(out_path) as f:
            content = f.read()
        self.assertIn("no changes vs HEAD", content)

    def test_bad_git_ref_exits_nonzero_with_stderr_relayed(self):
        result = run_script([self.plan_path, "1", "--base", "not-a-real-ref-xyz"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not-a-real-ref-xyz", result.stderr)

    def test_unknown_task_number_exits_nonzero(self):
        result = run_script([self.plan_path, "99", "--base", self.commit1])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Task 99", result.stderr)

    def test_fence_survives_backtick_lines_in_diff(self):
        doc_path = os.path.join(self.repo_dir, "doc.md")
        with open(doc_path, "w") as f:
            f.write("intro\n```\ncode\n```\nend\n")
        self._git("add", ".")
        self._git("commit", "-m", "add doc with fences")
        base = self._git_output("rev-parse", "HEAD").strip()
        with open(doc_path, "a") as f:
            f.write("changed tail\n")
        self._git("add", ".")
        self._git("commit", "-m", "change near fences")

        out_dir = tempfile.mkdtemp(prefix="review-packet-out-")
        self.addCleanup(shutil.rmtree, out_dir, ignore_errors=True)
        result = run_script([self.plan_path, "1", "--base", base, "--out", out_dir])
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(result.stdout.strip()) as f:
            lines = f.read().splitlines()

        open_idx, fence = next(
            (i, l[: len(l) - len(l.lstrip("`"))])
            for i, l in enumerate(lines)
            if l.startswith("`") and l.endswith("diff")
        )
        body = lines[open_idx + 1 : len(lines) - 1 - lines[::-1].index(fence)]
        self.assertIn(" ```", body)
        for line in body:
            stripped = line.lstrip(" ")
            run = len(stripped) - len(stripped.lstrip("`"))
            self.assertLess(run, len(fence), "diff body line closes the outer fence: %r" % line)

    def test_fenced_heading_does_not_terminate_task_block(self):
        # issue #12: a fenced markdown example containing '## ...' inside the
        # task must not end the block — that emits a silently thin packet.
        fenced_plan = os.path.join(self.repo_dir, "fenced_plan.md")
        with open(fenced_plan, "w") as f:
            f.write(
                "**Goal:** Ship it.\n\n"
                "### Task 1: Do it\n"
                "```markdown\n"
                "## Example section\n"
                "```\n"
                "tail line after fence\n\n"
                "### Task 2: Other\nbody\n"
            )
        self._git("add", ".")
        self._git("commit", "-m", "add fenced plan")

        out_dir = tempfile.mkdtemp(prefix="review-packet-out-")
        self.addCleanup(shutil.rmtree, out_dir, ignore_errors=True)
        result = run_script([fenced_plan, "1", "--base", "HEAD", "--out", out_dir])
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(result.stdout.strip()) as f:
            content = f.read()
        self.assertIn("## Example section", content)
        self.assertIn("tail line after fence", content)
        self.assertNotIn("### Task 2", content)

    def test_out_dir_honored_and_path_printed(self):
        out_dir = tempfile.mkdtemp(prefix="review-packet-out-")
        self.addCleanup(shutil.rmtree, out_dir, ignore_errors=True)
        result = run_script(
            [self.plan_path, "1", "--base", self.commit1, "--out", out_dir]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        out_path = result.stdout.strip()
        self.assertEqual(os.path.dirname(out_path), os.path.abspath(out_dir))
        self.assertEqual(os.path.basename(out_path), "task-1-review.md")


class ReviewPacketOutsideGitRepoTests(unittest.TestCase):
    def test_plan_outside_git_repo_exits_nonzero(self):
        non_repo_dir = tempfile.mkdtemp(prefix="review-packet-norepo-")
        try:
            plan_path = os.path.join(non_repo_dir, "plan.md")
            with open(plan_path, "w") as f:
                f.write(PLAN_TASK1)
            result = run_script([plan_path, "1", "--base", "HEAD"])
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(result.stderr.strip())
        finally:
            shutil.rmtree(non_repo_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
