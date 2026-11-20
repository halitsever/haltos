import unittest

from haltos_agents.layout import grouped, neighbour, sections


class GroupedTest(unittest.TestCase):
    groups = ["need", "need", "work", "done", "done", "done"]

    def test_each_group_starts_a_row(self):
        self.assertEqual(grouped(self.groups, 2), [(0, 0, 1, 1), (1, 0, 1, 1), (0, 1, 1, 1), (0, 2, 1, 1), (1, 2, 1, 1), (0, 3, 1, 1)])

    def test_sections_count_and_first_row(self):
        self.assertEqual(sections(self.groups, 2), [("need", 2, 0), ("work", 1, 1), ("done", 3, 2)])

    def test_empty(self):
        self.assertEqual((grouped([], 3), sections([], 3)), ([], []))


class NeighbourTest(unittest.TestCase):
    rects = grouped(["need", "work", "work", "work"], 3)

    def test_down_crosses_into_the_next_section(self):
        self.assertEqual(neighbour(self.rects, 0, "down"), 1)

    def test_up_into_a_short_row(self):
        self.assertEqual(neighbour(self.rects, 3, "up"), 0)

    def test_clamps_at_the_edges(self):
        self.assertEqual(neighbour(self.rects, 0, "up"), 0)
        self.assertEqual(neighbour(self.rects, 2, "down"), 2)


if __name__ == "__main__":
    unittest.main()
