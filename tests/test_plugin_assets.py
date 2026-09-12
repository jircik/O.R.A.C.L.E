import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_COMMANDS = {"oracle", "oracle-off", "oracle-setup", "oracle-plan", "oracle-status"}
EXPECTED_SKILLS = {"oracle-tutor", "oracle-setup", "oracle-plan", "oracle-status"}
CLI_SUBCOMMANDS = {
    "status", "init", "concepts-list", "concepts-set", "plan-save", "plan-show",
    "plan-list", "session-activate", "session-show", "session-deactivate",
    "log", "commit", "profile-set",
}


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return {}
    fields = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )

    def test_declares_name_and_description(self):
        self.assertEqual(self.manifest["name"], "oracle")
        self.assertTrue(self.manifest["description"])

    def test_registers_both_hooks(self):
        self.assertIn("UserPromptSubmit", self.manifest["hooks"])
        self.assertIn("SessionEnd", self.manifest["hooks"])

    def test_hook_scripts_exist(self):
        for event, groups in self.manifest["hooks"].items():
            for group in groups:
                for hook in group["hooks"]:
                    match = re.search(r"\$\{CLAUDE_PLUGIN_ROOT\}/(\S+?)\"", hook["command"])
                    self.assertIsNotNone(match, msg=f"{event}: {hook['command']}")
                    self.assertTrue(
                        (ROOT / match.group(1)).exists(), msg=f"missing: {match.group(1)}"
                    )

    def test_marketplace_points_at_this_plugin(self):
        marketplace = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        self.assertEqual([p["name"] for p in marketplace["plugins"]], ["oracle"])


class TestCommands(unittest.TestCase):
    def test_expected_commands_exist_with_descriptions(self):
        found = {p.stem for p in (ROOT / "commands").glob("*.md")}
        self.assertTrue(EXPECTED_COMMANDS.issubset(found), msg=f"found: {found}")
        for name in EXPECTED_COMMANDS:
            fields = frontmatter(ROOT / "commands" / f"{name}.md")
            self.assertTrue(fields.get("description"), msg=f"{name} has no description")


class TestSkills(unittest.TestCase):
    def test_expected_skills_have_valid_frontmatter(self):
        for name in EXPECTED_SKILLS:
            path = ROOT / "skills" / name / "SKILL.md"
            self.assertTrue(path.exists(), msg=f"missing skill: {name}")
            fields = frontmatter(path)
            self.assertEqual(fields.get("name"), name)
            self.assertTrue(fields.get("description"))


class TestNoInventedSubcommands(unittest.TestCase):
    """Prompts calling a CLI subcommand that does not exist fail silently at
    runtime. Catch it here instead."""

    def test_every_referenced_subcommand_exists(self):
        pattern = re.compile(r"oracle_store\.py\"?\s+([a-z][a-z-]+)")
        for path in list((ROOT / "skills").rglob("*.md")) + list(
            (ROOT / "commands").glob("*.md")
        ):
            for used in pattern.findall(path.read_text(encoding="utf-8")):
                self.assertIn(used, CLI_SUBCOMMANDS, msg=f"{path.name} uses '{used}'")


if __name__ == "__main__":
    unittest.main()
