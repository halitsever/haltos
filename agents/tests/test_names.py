import json
import os
import tempfile
import unittest
from pathlib import Path

from haltos_agents.names import age, recent_dirs, slug


class SlugTest(unittest.TestCase):
    def test_folds_turkish_and_keeps_four_words(self):
        self.assertEqual(slug("Şu meta etiketlerini düzelt lütfen", set()), "su-meta-etiketlerini-duzelt")

    def test_upper_case_turkish(self):
        self.assertEqual(slug("IĞDIR İÇİN ÖZET", set()), "igdir-icin-ozet")

    def test_punctuation_dropped(self):
        self.assertEqual(slug("fix: the README.md, now!", set()), "fix-the-readmemd-now")

    def test_at_most_30_chars_without_trailing_dash(self):
        s = slug("abcdefghijklmnop qrstuvwxyzabcdef ghij", set())
        self.assertLessEqual(len(s), 30)
        self.assertFalse(s.endswith("-"))

    def test_dedupes(self):
        self.assertEqual(slug("fix it", {"fix-it"}), "fix-it-2")
        self.assertEqual(slug("fix it", {"fix-it", "fix-it-2"}), "fix-it-3")

    def test_empty_prompt(self):
        self.assertEqual(slug("   ", set()), "agent")
        self.assertEqual(slug("!!!", {"agent"}), "agent-2")


class AgeTest(unittest.TestCase):
    def test_age(self):
        got = [age(s) for s in (0, 59, 61, 3599, 3600, 4320, -5)]
        self.assertEqual(got, ["0m", "0m", "1m", "59m", "1h0m", "1h12m", "0m"])


class RecentDirsTest(unittest.TestCase):
    def test_unique_existing_newest_first(self):
        tmp = Path(tempfile.mkdtemp())
        a, b = tmp / "a", tmp / "b"
        a.mkdir()
        b.mkdir()
        root = tmp / "projects"
        for name, cwd, mtime in [("1", a, 100), ("2", tmp / "gone", 300), ("3", b, 200), ("4", a, 400)]:
            p = root / "x" / f"{name}.jsonl"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"type": "user", "cwd": str(cwd)}) + "\n")
            os.utime(p, (mtime, mtime))
        self.assertEqual(recent_dirs(root), [str(a), str(b)])
        self.assertEqual(recent_dirs(root, limit=1), [str(a)])


if __name__ == "__main__":
    unittest.main()
