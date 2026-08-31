import json
import unittest
from pathlib import Path
from unittest.mock import patch

from lol_patch_scraper import (
    format_text,
    get_patch_name,
    parse_patch_notes,
    save_processed_output,
    save_raw_html,
)


HTML = """
<html><body><main>
<h1>League of Legends Patch 99.1 Notes</h1>
<div id="patch-notes-container">
  <header><h2>Patch Highlights</h2></header>
  <div><p>Cosmetics are here.</p></div>

  <header><h2>Champions</h2></header>
  <div>
    <h3>Annie</h3>
    <blockquote class="context">
      <p>Annie needs a small early-game buff.</p>
      <h4>Q - Disintegrate</h4>
    </blockquote>
    <ul><li>Damage: 10 ⇒ 20</li></ul>
  </div>

  <header><h2>Items</h2></header>
  <div><h3>Example Sword</h3><ul><li>AD: 40 ⇒ 45</li></ul></div>

  <header><h2>ARAM</h2></header>
  <div><h3>Annie</h3><ul><li>ARAM-only change</li></ul></div>

  <header><h2>Arena</h2></header>
  <div><h3>Annie</h3><ul><li>Arena-only change</li></ul></div>
</div></main></body></html>
"""


class PatchParserTests(unittest.TestCase):
    def test_keeps_sr_and_excludes_other_modes(self):
        patch = parse_patch_notes(HTML, "https://example.test")
        names = [section["name"] for section in patch["sections"]]

        self.assertEqual(names, ["Champions", "Items"])
        rendered = format_text(patch)
        self.assertIn("Damage: 10 ⇒ 20", rendered)
        self.assertNotIn("ARAM-only", rendered)
        self.assertNotIn("Arena-only", rendered)

    def test_context_is_included_by_default(self):
        patch = parse_patch_notes(HTML)
        champion = patch["sections"][0]["entries"][0]

        self.assertEqual(champion["context"], ["Annie needs a small early-game buff."])

    def test_context_can_be_disabled(self):
        patch = parse_patch_notes(HTML, include_context=False)
        champion = patch["sections"][0]["entries"][0]

        self.assertEqual(champion["context"], [])

    def test_missing_container_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, "patch-notes container"):
            parse_patch_notes("<html></html>")

    def test_raw_and_processed_files_use_separate_folders(self):
        url = "https://example.test/league-of-legends-patch-99-1-notes/"

        # Mock disk writes so this test does not leave test files behind.
        with (
            patch.object(Path, "mkdir") as make_folder,
            patch.object(Path, "write_text") as write_file,
        ):
            raw_path = save_raw_html(HTML, url)
            output_path = save_processed_output(
                json.dumps({"test": True}), url, is_json=True
            )

        self.assertEqual(get_patch_name(url), "patch-99-1")
        self.assertEqual(raw_path, Path("raw_data/patch-99-1.html"))
        self.assertEqual(output_path, Path("processed_data/patch-99-1.json"))
        self.assertEqual(make_folder.call_count, 2)
        self.assertEqual(write_file.call_count, 2)


if __name__ == "__main__":
    unittest.main()
