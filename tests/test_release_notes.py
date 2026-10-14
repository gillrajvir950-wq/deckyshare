"""Release notes shown in the panel (release_notes.py)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release_notes as rn  # noqa: E402

SAMPLE = """# Changelog

## v1.4.0

- **Clips**: shows `progress` and [details](https://example.com).
  
## v1.3.1

Security fixes:

- Phones can no longer browse files.
### Internal
- Second item

## v1.3.0

- Older entry
"""


class NotesTests(unittest.TestCase):
    def test_section_for_exact_version_is_plain_text(self):
        notes = rn.notes_for(SAMPLE, "1.4.0")
        self.assertEqual(notes["version"], "1.4.0")
        self.assertEqual(notes["lines"], [{"text": "Clips: shows progress and details.", "bullet": True}])

    def test_rc_falls_back_to_base_version_and_skips_subheadings(self):
        notes = rn.notes_for(SAMPLE, "v1.3.1-rc.2")
        self.assertEqual(notes["version"], "1.3.1")
        self.assertEqual([l["text"] for l in notes["lines"]], ["Security fixes:", "Phones can no longer browse files.", "Second item"])
        self.assertFalse(notes["lines"][0]["bullet"])

    def test_unknown_version_and_missing_file(self):
        self.assertEqual(rn.notes_for(SAMPLE, "9.9.9")["lines"], [])
        self.assertEqual(rn.installed_notes("/nonexistent", "1.0.0")["lines"], [])

    def test_bundled_changelog_has_notes_for_this_version(self):
        root = Path(__file__).resolve().parents[1]
        import json
        version = json.loads((root / "package.json").read_text())["version"]
        self.assertTrue(rn.installed_notes(root, version)["lines"], "CHANGELOG.md needs a section for " + version)


if __name__ == "__main__":
    unittest.main()
