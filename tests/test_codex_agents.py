import pathlib
import tempfile
import unittest

from scripts.update_codex_agents import BLOCK, END, LEGACY, START, update_agents


class CodexAgentsTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(prefix="doc2html-agents-test-")
        self.addCleanup(self.workspace.cleanup)
        self.path = pathlib.Path(self.workspace.name) / "AGENTS.md"

    def test_legacy_migration_preserves_rules_before_and_after_entry(self):
        prefix = "# Existing rules\nKeep the prefix.\n\n"
        suffix = "\n# Later rules\nKeep the suffix.\n"
        self.path.write_text(prefix + LEGACY + suffix)

        self.assertTrue(update_agents(self.path))
        self.assertEqual(self.path.read_text(), prefix + BLOCK + suffix)

    def test_update_is_idempotent(self):
        self.path.write_text("Existing instructions.\n")
        self.assertTrue(update_agents(self.path))
        saved = self.path.read_bytes()

        self.assertFalse(update_agents(self.path))
        self.assertEqual(self.path.read_bytes(), saved)

    def test_uninstall_preserves_rules_after_managed_entry(self):
        prefix = "Keep the prefix.\n\n"
        suffix = "\n# Other skill\nKeep these instructions.\n"
        self.path.write_text(prefix + BLOCK + suffix)

        self.assertTrue(update_agents(self.path, remove=True))
        self.assertEqual(self.path.read_text(), prefix + suffix)

    def test_uninstall_preserves_rules_after_legacy_entry(self):
        prefix = "Keep the prefix.\n"
        suffix = "\n# Later rules\nKeep the suffix.\n"
        self.path.write_text(prefix + LEGACY + suffix)

        self.assertTrue(update_agents(self.path, remove=True))
        self.assertEqual(self.path.read_text(), prefix + suffix)

    def test_unrelated_mention_and_custom_heading_are_preserved(self):
        original = "Use doc-to-html when appropriate.\n# doc-to-html（文档转 HTML）\nCustom user instructions.\n"
        self.path.write_text(original)

        self.assertTrue(update_agents(self.path))
        self.assertTrue(self.path.read_text().startswith(original))
        self.assertTrue(update_agents(self.path, remove=True))
        self.assertIn(original, self.path.read_text())

    def test_incomplete_managed_entry_does_not_modify_original_file(self):
        original = "Keep this.\n" + START + "\nIncomplete block.\n"
        self.path.write_text(original)

        with self.assertRaises(ValueError):
            update_agents(self.path)
        self.assertEqual(self.path.read_text(), original)

    def test_removal_without_entry_does_not_change_file_or_create_missing_file(self):
        self.assertFalse(update_agents(self.path, remove=True))
        self.assertFalse(self.path.exists())
        self.path.write_text("Existing rules.\n")
        saved = self.path.read_bytes()
        self.assertFalse(update_agents(self.path, remove=True))
        self.assertEqual(self.path.read_bytes(), saved)


if __name__ == "__main__":
    unittest.main()
