import unittest
from layout_math import cycle_tab_index, window_rail_bottom_reserve


class RailNavigationTests(unittest.TestCase):
    def test_next_previous(self):
        self.assertEqual(cycle_tab_index(0, 6, 1), 1)
        self.assertEqual(cycle_tab_index(3, 6, -1), 2)

    def test_wraps_both_ways(self):
        self.assertEqual(cycle_tab_index(5, 6, 1), 0)
        self.assertEqual(cycle_tab_index(0, 6, -1), 5)

    def test_no_tabs(self):
        self.assertEqual(cycle_tab_index(0, 0, 1), -1)
        self.assertEqual(cycle_tab_index(-1, -1, -1), -1)

    def test_one_tab(self):
        self.assertEqual(cycle_tab_index(0, 1, -1), 0)
        self.assertEqual(cycle_tab_index(0, 1, 1), 0)

    def test_bottom_margin_only_when_windowed(self):
        self.assertEqual(window_rail_bottom_reserve(True, 800), 0)
        self.assertEqual(window_rail_bottom_reserve(False, 800), 100)
        self.assertEqual(window_rail_bottom_reserve(False, 360), 100)
        self.assertEqual(window_rail_bottom_reserve(False, 270), 60)
        self.assertEqual(window_rail_bottom_reserve(False, 190), 0)


if __name__ == '__main__':
    unittest.main()
