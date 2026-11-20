import unittest

import haltos_agents


class IsGridTest(unittest.TestCase):
    def test_a_claudegrid_konsole_window_is_a_grid(self):
        self.assertTrue(haltos_agents.is_grid("konsole", "▦ halit — Konsole"))

    def test_other_konsole_windows_are_not(self):
        self.assertFalse(haltos_agents.is_grid("konsole", "~ : bash — Konsole"))

    def test_other_apps_named_like_a_grid_are_not(self):
        self.assertFalse(haltos_agents.is_grid("google-chrome", "▦ claudegrid"))


if __name__ == "__main__":
    unittest.main()
