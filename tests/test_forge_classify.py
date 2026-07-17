"""Classification engine: verdict parsing into Finding objects, diff line-range
extraction, runner-verified provenance, the disposition matrix, and the combined
classify_findings pass. Pure functions — no codex, no git, no plan loop."""
import unittest

from _forge_support import *  # noqa: F401,F403
import forge_common


# --- unified-diff fixtures (git-style, a/ b/ prefixes) ----------------------

DIFF_SINGLE = """diff --git a/foo.py b/foo.py
index 1111111..2222222 100644
--- a/foo.py
+++ b/foo.py
@@ -10,3 +12,5 @@ def f():
 context
+added_a
+added_b
 context
"""

DIFF_MULTI_HUNK = """diff --git a/foo.py b/foo.py
index 1111111..2222222 100644
--- a/foo.py
+++ b/foo.py
@@ -1,2 +1,3 @@
 a
+b
 c
@@ -10,2 +11,4 @@
 x
+y
+z
 w
"""

DIFF_MULTI_FILE = """diff --git a/foo.py b/foo.py
index 1111111..2222222 100644
--- a/foo.py
+++ b/foo.py
@@ -1,1 +1,2 @@
 a
+b
diff --git a/bar.py b/bar.py
index 3333333..4444444 100644
--- a/bar.py
+++ b/bar.py
@@ -5,1 +7,3 @@
 x
+y
+z
"""

DIFF_ADDED_ONLY = """diff --git a/new.py b/new.py
new file mode 100644
index 0000000..5555555
--- /dev/null
+++ b/new.py
@@ -0,0 +1,3 @@
+line1
+line2
+line3
"""

DIFF_SINGLE_LINE_HUNK = """diff --git a/foo.py b/foo.py
index 1111111..2222222 100644
--- a/foo.py
+++ b/foo.py
@@ -5 +7 @@
-old
+new
"""


def _finding(**kw):
    """Build a Finding with sane defaults so each test names only the axes it
    exercises."""
    base = dict(
        id="f1",
        summary="one line",
        file="foo.py",
        lines="13",
        provenance="in-diff",
        impact="improvement",
        contract_ref=None,
    )
    base.update(kw)
    return forge_common.Finding(**base)


class DiffLineRangesTests(unittest.TestCase):
    """diff_line_ranges: new-side changed line ranges per file, from unified-diff
    hunk headers (@@ -a,b +c,d @@)."""

    def test_single_hunk(self):
        ranges = forge_run.diff_line_ranges(DIFF_SINGLE)
        self.assertEqual(ranges, {"foo.py": [(12, 16)]})

    def test_multiple_hunks_one_file(self):
        ranges = forge_run.diff_line_ranges(DIFF_MULTI_HUNK)
        self.assertEqual(ranges, {"foo.py": [(1, 3), (11, 14)]})

    def test_multiple_files(self):
        ranges = forge_run.diff_line_ranges(DIFF_MULTI_FILE)
        self.assertEqual(ranges, {"foo.py": [(1, 2)], "bar.py": [(7, 9)]})

    def test_added_only_hunk_against_dev_null(self):
        ranges = forge_run.diff_line_ranges(DIFF_ADDED_ONLY)
        self.assertEqual(ranges, {"new.py": [(1, 3)]})

    def test_single_line_hunk_header_no_count(self):
        # `@@ -5 +7 @@` — omitted counts default to 1, so the new side is line 7.
        ranges = forge_run.diff_line_ranges(DIFF_SINGLE_LINE_HUNK)
        self.assertEqual(ranges, {"foo.py": [(7, 7)]})

    def test_empty_diff(self):
        self.assertEqual(forge_run.diff_line_ranges(""), {})


class VerifyProvenanceTests(unittest.TestCase):
    """verify_provenance: intersect the finding's lines with the diff's changed
    ranges for that file — in-diff on overlap, pre-existing otherwise, regardless
    of the reviewer's claim."""

    def setUp(self):
        self.ranges = {"foo.py": [(12, 16)]}

    def test_inside_range_is_in_diff(self):
        f = _finding(file="foo.py", lines="13-14")
        self.assertEqual(forge_run.verify_provenance(f, self.ranges), "in-diff")

    def test_single_line_on_boundary_is_in_diff(self):
        f = _finding(file="foo.py", lines="12")
        self.assertEqual(forge_run.verify_provenance(f, self.ranges), "in-diff")

    def test_outside_range_is_pre_existing(self):
        f = _finding(file="foo.py", lines="40-42")
        self.assertEqual(forge_run.verify_provenance(f, self.ranges), "pre-existing")

    def test_file_not_in_diff_is_pre_existing(self):
        f = _finding(file="other.py", lines="13")
        self.assertEqual(forge_run.verify_provenance(f, self.ranges), "pre-existing")

    def test_reviewer_in_diff_claim_overridden_when_lines_outside(self):
        # Reviewer optimistically labels it in-diff, but the lines fall outside
        # every changed range — the runner overrides to pre-existing.
        f = _finding(file="foo.py", lines="40", provenance="in-diff")
        self.assertEqual(forge_run.verify_provenance(f, self.ranges), "pre-existing")


class DeriveDispositionTests(unittest.TestCase):
    """derive_disposition: the four-quadrant matrix over verified provenance and
    the contract_ref-gated impact."""

    def test_in_diff_contract_breaking_is_fix(self):
        f = _finding(provenance="in-diff", impact="contract-breaking",
                     contract_ref="AC1: acceptance passes")
        self.assertEqual(forge_run.derive_disposition(f), "fix")

    def test_in_diff_improvement_is_defer(self):
        f = _finding(provenance="in-diff", impact="improvement", contract_ref=None)
        self.assertEqual(forge_run.derive_disposition(f), "defer")

    def test_pre_existing_contract_breaking_is_halt(self):
        f = _finding(provenance="pre-existing", impact="contract-breaking",
                     contract_ref="§ Disposition matrix")
        self.assertEqual(forge_run.derive_disposition(f), "halt")

    def test_pre_existing_improvement_is_defer(self):
        f = _finding(provenance="pre-existing", impact="improvement", contract_ref=None)
        self.assertEqual(forge_run.derive_disposition(f), "defer")

    def test_null_contract_ref_downgrades_contract_breaking_to_defer(self):
        # in-diff + contract-breaking would be `fix`, but a null contract_ref
        # strips the contract-breaking claim (named-evidence rule) → improvement
        # → defer.
        f = _finding(provenance="in-diff", impact="contract-breaking", contract_ref=None)
        self.assertEqual(forge_run.derive_disposition(f), "defer")

    def test_null_contract_ref_downgrades_pre_existing_halt_to_defer(self):
        # pre-existing + contract-breaking would be `halt`, but a null contract_ref
        # downgrades it to improvement → defer, never a scope-halt on unnamed
        # evidence.
        f = _finding(provenance="pre-existing", impact="contract-breaking",
                     contract_ref=None)
        self.assertEqual(forge_run.derive_disposition(f), "defer")


class ParseVerdictTests(unittest.TestCase):
    """parse_verdict on the per-finding schema: pass, a well-formed findings
    verdict, last-object-wins, and the loud contract errors."""

    def test_bare_pass(self):
        v = forge_run.parse_verdict('{"verdict": "pass"}')
        self.assertEqual(v.kind, "pass")
        self.assertEqual(v.findings, [])

    def test_findings_parsed_into_finding_objects(self):
        msg = (
            "Here is my review.\n\n"
            "```json\n"
            '{"verdict": "findings", "findings": ['
            '{"id": "f1", "summary": "missing guard", '
            '"location": {"file": "a.py", "lines": "3-5"}, '
            '"provenance": "in-diff", "impact": "contract-breaking", '
            '"contract_ref": "AC1: guard present", '
            '"repair_task": null}]}\n'
            "```\nThat is all.\n"
        )
        v = forge_run.parse_verdict(msg)
        self.assertEqual(v.kind, "findings")
        self.assertEqual(len(v.findings), 1)
        f = v.findings[0]
        self.assertIsInstance(f, forge_common.Finding)
        self.assertEqual(f.id, "f1")
        self.assertEqual(f.summary, "missing guard")
        self.assertEqual(f.file, "a.py")
        self.assertEqual(f.lines, "3-5")
        self.assertEqual(f.provenance, "in-diff")
        self.assertEqual(f.impact, "contract-breaking")
        self.assertEqual(f.contract_ref, "AC1: guard present")

    def test_improvement_finding_may_omit_location(self):
        # Only contract-breaking findings must carry a location; an improvement
        # finding without one parses (file/lines default to None).
        msg = (
            '{"verdict": "findings", "findings": ['
            '{"id": "f1", "summary": "nit", "impact": "improvement", '
            '"contract_ref": null}]}'
        )
        v = forge_run.parse_verdict(msg)
        self.assertEqual(v.kind, "findings")
        self.assertIsNone(v.findings[0].file)
        self.assertIsNone(v.findings[0].lines)

    def test_last_matching_object_wins(self):
        msg = (
            '{"verdict": "pass"}\n'
            "on reflection...\n"
            '{"verdict": "findings", "findings": ['
            '{"id": "f1", "summary": "x", '
            '"location": {"file": "a.py", "lines": "1"}, '
            '"impact": "improvement", "contract_ref": null}]}'
        )
        v = forge_run.parse_verdict(msg)
        self.assertEqual(v.kind, "findings")
        self.assertEqual(v.findings[0].id, "f1")

    def test_unparseable_prose_raises_naming_cause(self):
        with self.assertRaises(RuntimeError) as ctx:
            forge_run.parse_verdict("Looks good to me, ship it.")
        self.assertIn("verdict", str(ctx.exception).lower())

    def test_malformed_json_raises(self):
        with self.assertRaises(RuntimeError):
            forge_run.parse_verdict('{"verdict": ')

    def test_contract_breaking_missing_location_raises(self):
        msg = (
            '{"verdict": "findings", "findings": ['
            '{"id": "f1", "summary": "broken", '
            '"impact": "contract-breaking", "contract_ref": "AC1"}]}'
        )
        with self.assertRaises(RuntimeError) as ctx:
            forge_run.parse_verdict(msg)
        self.assertIn("location", str(ctx.exception).lower())

    def test_contract_breaking_missing_lines_raises(self):
        # location present but lines omitted is still incomplete for a
        # contract-breaking finding.
        msg = (
            '{"verdict": "findings", "findings": ['
            '{"id": "f1", "summary": "broken", '
            '"location": {"file": "a.py"}, '
            '"impact": "contract-breaking", "contract_ref": "AC1"}]}'
        )
        with self.assertRaises(RuntimeError):
            forge_run.parse_verdict(msg)


class ClassifyFindingsTests(unittest.TestCase):
    """classify_findings: end-to-end, sets each finding's runner-verified
    provenance and derived disposition against the actual diff."""

    def test_pass_verdict_returns_unchanged(self):
        v = forge_common.Verdict(kind="pass")
        out = forge_run.classify_findings(v, DIFF_SINGLE)
        self.assertIs(out, v)
        self.assertEqual(out.kind, "pass")

    def test_sets_verified_provenance_and_disposition(self):
        # f1: in the diff (foo.py 13 ∈ [12,16]) + contract-breaking → fix.
        # f2: claims in-diff but foo.py 40 is outside → overridden pre-existing;
        #     contract-breaking → halt.
        f1 = _finding(id="f1", file="foo.py", lines="13", provenance="pre-existing",
                      impact="contract-breaking", contract_ref="AC1")
        f2 = _finding(id="f2", file="foo.py", lines="40", provenance="in-diff",
                      impact="contract-breaking", contract_ref="AC2")
        v = forge_common.Verdict(kind="findings", findings=[f1, f2])
        out = forge_run.classify_findings(v, DIFF_SINGLE)
        self.assertEqual(f1.provenance, "in-diff")
        self.assertEqual(f1.disposition, "fix")
        self.assertEqual(f2.provenance, "pre-existing")
        self.assertEqual(f2.disposition, "halt")

    def test_null_contract_ref_defers_in_classify(self):
        f = _finding(id="f1", file="foo.py", lines="13", provenance="in-diff",
                     impact="contract-breaking", contract_ref=None)
        v = forge_common.Verdict(kind="findings", findings=[f])
        forge_run.classify_findings(v, DIFF_SINGLE)
        self.assertEqual(f.provenance, "in-diff")
        self.assertEqual(f.disposition, "defer")


if __name__ == "__main__":
    unittest.main()
