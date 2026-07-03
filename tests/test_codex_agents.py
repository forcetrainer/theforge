"""Tests for the Codex TOML tier agents (codex/agents/*.toml).

Validates: each TOML file parses via tomllib; required fields are present;
model / model_reasoning_effort match the spec's tier mapping table exactly;
nickname_candidates are unique, non-empty, tier-prefixed, and use only
ASCII letters/digits/spaces/hyphens/underscores; developer_instructions is
verbatim-identical (whitespace-normalized) to the body of the corresponding
agents/*.md file, below its frontmatter -- sync divergence is a bug.
"""
import pathlib
import re
import tomllib
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CODEX_AGENTS_DIR = REPO_ROOT / "codex" / "agents"
CLAUDE_AGENTS_DIR = REPO_ROOT / "agents"

# tier -> (model, model_reasoning_effort)
TIER_MAPPING = {
    "forge-light": ("gpt-5.4-mini", "low"),
    "forge-standard": ("gpt-5.4", "high"),
    "forge-deep": ("gpt-5.5", "xhigh"),
}

NICKNAME_CHARS_RE = re.compile(r"^[A-Za-z0-9 _-]+$")

REQUIRED_FIELDS = (
    "name",
    "description",
    "developer_instructions",
    "model",
    "model_reasoning_effort",
    "nickname_candidates",
)


def _load_toml(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def _md_frontmatter_and_body(path):
    """Split a Claude agent .md file into (frontmatter_dict, body_text)."""
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} does not start with frontmatter"
    _, rest = text.split("---\n", 1)
    frontmatter_text, body = rest.split("---\n", 1)
    frontmatter = {}
    for line in frontmatter_text.splitlines():
        if not line.strip():
            continue
        key, _, value = line.partition(":")
        frontmatter[key.strip()] = value.strip()
    return frontmatter, body


def _normalize_whitespace(text):
    return text.strip()


class CodexTierAgentTomlParsesTests(unittest.TestCase):
    def test_forge_light_parses(self):
        self.assertIsInstance(_load_toml(CODEX_AGENTS_DIR / "forge-light.toml"), dict)

    def test_forge_standard_parses(self):
        self.assertIsInstance(_load_toml(CODEX_AGENTS_DIR / "forge-standard.toml"), dict)

    def test_forge_deep_parses(self):
        self.assertIsInstance(_load_toml(CODEX_AGENTS_DIR / "forge-deep.toml"), dict)


class CodexTierAgentRequiredFieldsTests(unittest.TestCase):
    def test_required_fields_present(self):
        for tier in TIER_MAPPING:
            with self.subTest(tier=tier):
                agent = _load_toml(CODEX_AGENTS_DIR / f"{tier}.toml")
                for field in REQUIRED_FIELDS:
                    self.assertIn(field, agent, f"{tier}.toml missing field {field!r}")

    def test_name_matches_filename_stem(self):
        for tier in TIER_MAPPING:
            with self.subTest(tier=tier):
                agent = _load_toml(CODEX_AGENTS_DIR / f"{tier}.toml")
                self.assertEqual(agent["name"], tier)


class CodexTierAgentModelMappingTests(unittest.TestCase):
    def test_model_and_effort_match_spec_mapping(self):
        for tier, (model, effort) in TIER_MAPPING.items():
            with self.subTest(tier=tier):
                agent = _load_toml(CODEX_AGENTS_DIR / f"{tier}.toml")
                self.assertEqual(agent["model"], model)
                self.assertEqual(agent["model_reasoning_effort"], effort)


class CodexTierAgentNicknameCandidatesTests(unittest.TestCase):
    def test_nickname_candidates_unique_nonempty_tier_prefixed_and_valid_chars(self):
        for tier in TIER_MAPPING:
            with self.subTest(tier=tier):
                agent = _load_toml(CODEX_AGENTS_DIR / f"{tier}.toml")
                candidates = agent["nickname_candidates"]
                self.assertTrue(len(candidates) >= 1)
                self.assertEqual(len(candidates), len(set(candidates)), "duplicate nicknames")
                for name in candidates:
                    self.assertTrue(name, "empty nickname")
                    self.assertTrue(
                        name.startswith(tier),
                        f"nickname {name!r} is not prefixed with tier {tier!r}",
                    )
                    self.assertRegex(name, NICKNAME_CHARS_RE)

    def test_nickname_candidates_five_per_tier(self):
        for tier in TIER_MAPPING:
            with self.subTest(tier=tier):
                agent = _load_toml(CODEX_AGENTS_DIR / f"{tier}.toml")
                expected = [f"{tier}-{i}" for i in range(1, 6)]
                self.assertEqual(agent["nickname_candidates"], expected)


class CodexTierAgentDeveloperInstructionsSyncTests(unittest.TestCase):
    def test_developer_instructions_matches_corresponding_md_body(self):
        for tier in TIER_MAPPING:
            with self.subTest(tier=tier):
                agent = _load_toml(CODEX_AGENTS_DIR / f"{tier}.toml")
                _, body = _md_frontmatter_and_body(CLAUDE_AGENTS_DIR / f"{tier}.md")
                self.assertEqual(
                    _normalize_whitespace(agent["developer_instructions"]),
                    _normalize_whitespace(body),
                )

    def test_description_matches_corresponding_md_frontmatter(self):
        for tier in TIER_MAPPING:
            with self.subTest(tier=tier):
                agent = _load_toml(CODEX_AGENTS_DIR / f"{tier}.toml")
                frontmatter, _ = _md_frontmatter_and_body(CLAUDE_AGENTS_DIR / f"{tier}.md")
                self.assertEqual(agent["description"], frontmatter["description"])


if __name__ == "__main__":
    unittest.main()
