import tempfile
import unittest
from pathlib import Path

from haltos_agents.hidden import add, load


class HiddenTest(unittest.TestCase):
    def setUp(self):
        self.p = Path(tempfile.mkdtemp()) / "state" / "hidden.json"

    def test_missing_file_is_empty(self):
        self.assertEqual(load(self.p), set())

    def test_add_persists_once(self):
        add(self.p, "a")
        add(self.p, "a")
        add(self.p, "b")
        self.assertEqual(load(self.p), {"a", "b"})

    def test_corrupt_file_is_empty_and_add_recovers(self):
        self.p.parent.mkdir(parents=True)
        self.p.write_text("{")
        self.assertEqual(load(self.p), set())
        add(self.p, "a")
        self.assertEqual(load(self.p), {"a"})


if __name__ == "__main__":
    unittest.main()
