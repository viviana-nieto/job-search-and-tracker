"""Assert SKILL.md and .claude/commands/job-search.md share the same body.

The project ships two slash-command files for two install paths:

1. SKILL.md at the repo root — picked up by Claude Code's global skill loader
   when the user clones into ~/.claude/skills/job-search/.
2. .claude/commands/job-search.md — picked up by Claude Code's project-local
   loader when the user clones into a normal projects folder and opens the
   directory in Claude Code.

Both files contain the same runbook (~650 lines). SKILL.md additionally has
YAML frontmatter and a "Project location" preamble at the top. From the
"## How to execute" header onward, the two files MUST be byte-identical so
the slash command behaves the same regardless of which install path the user
took.

This test extracts the shared body from each file (everything from the
"## How to execute" marker to end-of-file) and asserts equality.
"""

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SKILL_MD = PROJECT_ROOT / "SKILL.md"
PROJECT_LOCAL = PROJECT_ROOT / ".claude" / "commands" / "job-search.md"

SHARED_BODY_MARKER = "## How to execute"


def _shared_body(text: str) -> str:
    """Return everything from the shared body marker to end of file."""
    idx = text.find(SHARED_BODY_MARKER)
    if idx == -1:
        raise ValueError(
            f"Marker {SHARED_BODY_MARKER!r} not found. Both skill files must "
            "contain this header so the sync test can locate the shared body."
        )
    return text[idx:]


class TestSkillFilesInSync(unittest.TestCase):
    def test_both_files_exist(self):
        self.assertTrue(SKILL_MD.exists(), f"Expected SKILL.md at {SKILL_MD}")
        self.assertTrue(
            PROJECT_LOCAL.exists(),
            f"Expected project-local skill at {PROJECT_LOCAL}",
        )

    def test_shared_body_is_byte_identical(self):
        skill_body = _shared_body(SKILL_MD.read_text())
        local_body = _shared_body(PROJECT_LOCAL.read_text())
        if skill_body == local_body:
            return
        # Find the first differing line so the failure message is actionable.
        skill_lines = skill_body.splitlines()
        local_lines = local_body.splitlines()
        for i, (a, b) in enumerate(zip(skill_lines, local_lines)):
            if a != b:
                self.fail(
                    f"SKILL.md and .claude/commands/job-search.md diverge at "
                    f"line {i + 1} of the shared body:\n"
                    f"  SKILL.md:        {a!r}\n"
                    f"  job-search.md:   {b!r}"
                )
        if len(skill_lines) != len(local_lines):
            self.fail(
                f"Shared bodies are different lengths: "
                f"SKILL.md has {len(skill_lines)} lines, "
                f".claude/commands/job-search.md has {len(local_lines)} lines."
            )

    def test_skill_md_has_frontmatter(self):
        text = SKILL_MD.read_text()
        self.assertTrue(
            text.startswith("---\n"),
            "SKILL.md must start with YAML frontmatter for Claude Code's skill "
            "loader to register it.",
        )
        # Frontmatter should include name and description fields.
        end_marker_idx = text.find("\n---\n", 4)
        self.assertNotEqual(
            end_marker_idx,
            -1,
            "SKILL.md frontmatter is missing a closing '---' line.",
        )
        frontmatter = text[4:end_marker_idx]
        self.assertIn("name:", frontmatter, "Frontmatter must include name:")
        self.assertIn(
            "description:",
            frontmatter,
            "Frontmatter must include description:",
        )

    def test_project_local_file_has_no_frontmatter(self):
        text = PROJECT_LOCAL.read_text()
        self.assertFalse(
            text.startswith("---\n"),
            ".claude/commands/job-search.md should not have YAML frontmatter; "
            "Claude Code's project-local loader doesn't require it and the "
            "first line should be the title heading.",
        )


if __name__ == "__main__":
    unittest.main()
