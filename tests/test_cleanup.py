import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts.md2html import cleanup_paths


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(prefix="doc2html-cleanup-test-")
        self.addCleanup(self.workspace.cleanup)
        self.root = pathlib.Path(self.workspace.name)

    def write(self, relative, content="fixture"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_html_files_survive_while_intermediate_files_are_removed(self):
        pages = [self.write("final" + suffix, "final page")
                 for suffix in (".html", ".htm", ".HTML", ".HTM")]
        draft = self.write("assembled.md")

        removed, skipped = cleanup_paths([str(p) for p in pages + [draft]], set())

        self.assertEqual(removed, [str(draft)])
        self.assertEqual({p for p, _ in skipped}, {str(p) for p in pages})
        for page in pages:
            self.assertEqual(page.read_text(), "final page")
        self.assertFalse(draft.exists())

    def test_standalone_cleanup_preserves_direct_and_nested_html(self):
        for index, relative in enumerate(("final.html", "nested/final.HTM")):
            with self.subTest(relative=relative):
                directory = self.root / f"case-{index}"
                page = directory / relative
                page.parent.mkdir(parents=True)
                page.write_text("final page")
                draft = directory / "assembled.md"
                draft.write_text("draft")

                removed, skipped = cleanup_paths([str(directory)], set())

                self.assertEqual(removed, [])
                self.assertEqual(len(skipped), 1)
                self.assertEqual(page.read_text(), "final page")
                self.assertTrue(draft.exists())

    def test_directories_without_html_are_still_removed(self):
        draft = self.write("extracts/nested/draft.md")
        directory = self.root / "extracts"

        removed, skipped = cleanup_paths([str(directory)], set())

        self.assertEqual(removed, [str(directory)])
        self.assertEqual(skipped, [])
        self.assertFalse(draft.exists())
        self.assertFalse(directory.exists())

    def test_protected_output_and_its_ancestors_survive_without_html_suffix(self):
        page = self.write("output/nested/final-page", "final page")
        draft = self.write("separate-draft.md")
        targets = [self.root / "output", page.parent, page, draft]
        protected = {pathlib.Path(os.path.relpath(page))}

        removed, skipped = cleanup_paths([str(p) for p in targets], protected)

        self.assertEqual(removed, [str(draft)])
        self.assertEqual(len(skipped), 3)
        self.assertEqual(page.read_text(), "final page")
        self.assertFalse(draft.exists())

    def test_relative_cleanup_path_preserves_nested_output(self):
        page = self.write("output/nested/final.html", "final page")
        directory = pathlib.Path(os.path.relpath(self.root / "output"))

        removed, skipped = cleanup_paths([str(directory)], {page})

        self.assertEqual(removed, [])
        self.assertEqual(len(skipped), 1)
        self.assertEqual(page.read_text(), "final page")

    def test_cleanup_preserves_output_path_through_a_symlink(self):
        page = self.write("external/final-page", "final page")
        directory = self.root / "output"
        directory.mkdir()
        link = directory / "pages"
        link.symlink_to(page.parent, target_is_directory=True)
        output = link / page.name

        removed, skipped = cleanup_paths([str(directory)], {output})

        self.assertEqual(removed, [])
        self.assertEqual(len(skipped), 1)
        self.assertTrue(link.is_symlink())
        self.assertEqual(output.read_text(), "final page")

    def test_symlink_directory_is_skipped_without_removing_its_target(self):
        draft = self.write("extracts/draft.md")
        link = self.root / "extracts-link"
        link.symlink_to(draft.parent, target_is_directory=True)

        removed, skipped = cleanup_paths([str(link)], set())

        self.assertEqual(removed, [])
        self.assertEqual(len(skipped), 1)
        self.assertTrue(link.is_symlink())
        self.assertTrue(draft.exists())

    def test_failed_directory_scan_leaves_files_untouched(self):
        draft = self.write("extracts/draft.md")

        with mock.patch("scripts.md2html.os.scandir", side_effect=PermissionError("denied")):
            removed, skipped = cleanup_paths([str(draft.parent)], set())

        self.assertEqual(removed, [])
        self.assertEqual(len(skipped), 1)
        self.assertTrue(draft.exists())

    def test_missing_cleanup_path_is_skipped(self):
        missing = self.root / "missing.md"

        removed, skipped = cleanup_paths([str(missing)], set())

        self.assertEqual(removed, [])
        self.assertEqual(len(skipped), 1)
        self.assertFalse(missing.exists())

    def test_cleanup_cli_preserves_html_and_removes_separate_intermediates(self):
        page = self.write("output/nested/final.html", "final page")
        draft = self.write("extracts/draft.md")
        script = pathlib.Path(__file__).resolve().parents[1] / "scripts/md2html.py"

        result = subprocess.run(
            [sys.executable, str(script), "--cleanup", str(self.root / "output"), str(draft.parent)],
            capture_output=True, text=True, check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(page.read_text(), "final page")
        self.assertFalse(draft.parent.exists())


if __name__ == "__main__":
    unittest.main()
