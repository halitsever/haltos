import unittest

from haltos_agents import screen


@unittest.skipIf(screen.pyte is None, "pyte not installed")
class ScreenTest(unittest.TestCase):
    def test_plain_text_keeps_its_spaces(self):
        s = screen.Screen(8, 2)
        s.feed(b"a b")
        self.assertEqual(s.rows()[0], "a&nbsp;b&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;")
        self.assertEqual(len(s.rows()), 2)

    def test_colours_map_to_haltmono(self):
        s = screen.Screen(6, 1)
        s.feed(b"\x1b[31mred\x1b[0m!")
        row = s.rows()[0]
        self.assertIn('<span style="color:#ef4444">red</span>', row)
        self.assertIn("!", row)

    def test_true_colour_and_bold(self):
        s = screen.Screen(4, 1)
        s.feed(b"\x1b[1;38;2;255;135;0mx")
        self.assertIn("color:#ff8700", s.rows()[0])
        self.assertIn("font-weight:bold", s.rows()[0])

    def test_reverse_swaps_colours(self):
        s = screen.Screen(2, 1)
        s.feed(b"\x1b[7mx")
        self.assertIn(f"color:{screen.BG};background-color:{screen.FG}", s.rows()[0])

    def test_markup_is_escaped(self):
        s = screen.Screen(6, 1)
        s.feed(b"<a&b>")
        self.assertTrue(s.rows()[0].startswith("&lt;a&amp;b&gt;"))

    def test_cursor_and_resize(self):
        s = screen.Screen(10, 3)
        s.feed(b"ab\r\ncd")
        self.assertEqual(s.cursor(), (2, 1, True))
        s.resize(20, 5)
        self.assertEqual((len(s.rows()), s.cols), (5, 20))

    def test_changed_flag(self):
        s = screen.Screen(4, 1)
        self.assertTrue(s.take_changed())
        self.assertFalse(s.take_changed())
        s.feed(b"x")
        self.assertTrue(s.take_changed())


if __name__ == "__main__":
    unittest.main()
