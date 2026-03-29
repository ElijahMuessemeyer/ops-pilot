from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ops_pilot.parsing import chunk_document, load_documents


class ParsingTests(unittest.TestCase):
    def test_load_documents_reads_markdown_and_csv(self) -> None:
        documents = load_documents(
            [
                ROOT / "data" / "examples" / "club_ops_notes.md",
                ROOT / "data" / "examples" / "club_metrics.csv",
            ]
        )

        self.assertEqual(len(documents), 2)
        self.assertEqual(documents[0].name, "club_ops_notes.md")
        self.assertIn("weekly_follow_up_items", documents[1].content)

    def test_chunk_document_creates_searchable_segments(self) -> None:
        document = load_documents([ROOT / "data" / "examples" / "club_ops_notes.md"])[0]
        chunks = chunk_document(document, max_chars=180)

        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(any("6.5 hours per week" in chunk.text for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
