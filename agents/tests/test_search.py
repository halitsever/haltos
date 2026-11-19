import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from haltos_agents.search import Index, fold


def session(path, prompts, answer="", title=None, cwd="/home/u/halit.org", mtime=None):
    rows = [{"type": "user", "message": {"content": p}, "cwd": cwd} for p in prompts]
    if answer:
        rows.append({"type": "assistant", "message": {"content": [{"type": "text", "text": answer}]}, "cwd": cwd})
    if title:
        rows.append({"type": "ai-title", "aiTitle": title})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    if mtime:
        os.utime(path, (mtime, mtime))


class SearchTest(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.root = tmp / "projects"
        session(self.root / "p" / "s1.jsonl", ["meta etiketlerini düzelt"], "Ajan çalışıyor.", title="SEO meta düzeltme", mtime=1000)
        session(self.root / "p" / "s2.jsonl", ["kahvefalin içerik denetimi"], cwd="/home/u/kahvefalin.net", mtime=2000)
        session(self.root / "q" / "s3.jsonl", ["meta etiketleri ikinci tur"], cwd="/home/u/haltos", mtime=3000)
        self.index = Index(tmp / "index.sqlite")
        self.assertEqual(self.index.update(self.root), 3)
        self.addCleanup(self.index.close)

    def test_finds_prompt_and_reports_title_and_cwd(self):
        hits = self.index.search("etiketlerini")
        self.assertEqual([(h.session_id, h.title, h.cwd) for h in hits], [("s1", "SEO meta düzeltme", "/home/u/halit.org")])

    def test_title_falls_back_to_first_prompt(self):
        self.assertEqual(self.index.search("kahvefalin")[0].title, "kahvefalin içerik denetimi")

    def test_newest_first(self):
        self.assertEqual([h.session_id for h in self.index.search("meta")], ["s3", "s1"])

    def test_snippet_shows_original_text(self):
        self.assertIn("çalışıyor", self.index.search("ÇALIŞIYOR")[0].snippet)

    def test_turkish_dotless_i_matches_both_cases(self):
        self.assertEqual([h.session_id for h in self.index.search("ÇALIŞIYOR")], ["s1"])
        self.assertEqual([h.session_id for h in self.index.search("içerik")], ["s2"])
        self.assertEqual([h.session_id for h in self.index.search("İÇERİK")], ["s2"])

    def test_fts_syntax_is_literal(self):
        for q in ['"', "foo*", "-x", "AND", "(a", "a OR", "'", "NEAR(", "^meta"]:
            self.index.search(q)

    def test_blank_query_returns_nothing(self):
        self.assertEqual(self.index.search("   "), [])

    def test_incremental_update(self):
        self.assertEqual(self.index.update(self.root), 0)
        session(self.root / "p" / "s2.jsonl", ["yeni metin"], mtime=time.time())
        self.assertEqual(self.index.update(self.root), 1)
        self.assertEqual([h.session_id for h in self.index.search("yeni")], ["s2"])
        self.assertEqual(self.index.search("kahvefalin"), [])

    def test_deleted_transcript_drops_out(self):
        (self.root / "p" / "s1.jsonl").unlink()
        self.index.update(self.root)
        self.assertEqual(self.index.search("etiketlerini"), [])

    def test_fold(self):
        self.assertEqual(fold("IĞDIR İzmir ılık"), "iğdir izmir ilik")


if __name__ == "__main__":
    unittest.main()
