import unittest

from haltos_agents.layout import neighbour, pack


class PackTest(unittest.TestCase):
    def test_spotlight_takes_two_by_two_at_its_turn(self):
        self.assertEqual(pack(5, 1, 3, 2), [(0, 0, 1, 1), (1, 0, 2, 2), (0, 1, 1, 1), (0, 2, 1, 1), (1, 2, 1, 1)])

    def test_spotlight_after_a_full_row(self):
        self.assertEqual(pack(4, 3, 3, 2), [(0, 0, 1, 1), (1, 0, 1, 1), (2, 0, 1, 1), (0, 1, 2, 2)])

    def test_two_columns_spotlight_spans_both(self):
        self.assertEqual(pack(3, 0, 2, 3), [(0, 0, 2, 3), (0, 3, 1, 1), (1, 3, 1, 1)])

    def test_one_column(self):
        self.assertEqual(pack(2, 1, 1, 2), [(0, 0, 1, 1), (0, 1, 1, 2)])

    def test_no_selection_is_all_small(self):
        self.assertEqual(pack(2, -1, 3, 2), [(0, 0, 1, 1), (1, 0, 1, 1)])


# pack(6, 1, 3, 2) == [(0,0,1,1), (1,0,2,2), (0,1,1,1), (0,2,1,1), (1,2,1,1), (2,2,1,1)]
class NeighbourTest(unittest.TestCase):
    def test_down_picks_nearest_centre_below(self):
        rects = pack(6, 1, 3, 2)
        self.assertEqual(neighbour(rects, 1, "down"), 4)  # tiles 4 and 5 tie on |dx|, lower index wins
        self.assertEqual(neighbour(rects, 0, "down"), 2)

    def test_up_prefers_nearest_bottom_edge_then_centre(self):
        self.assertEqual(neighbour(pack(6, 1, 3, 2), 4, "up"), 1)

    def test_up_and_down_clamp(self):
        rects = pack(3, 0, 3, 2)
        self.assertEqual(neighbour(rects, 0, "up"), 0)
        self.assertEqual(neighbour(rects, 2, "down"), 2)


if __name__ == "__main__":
    unittest.main()
