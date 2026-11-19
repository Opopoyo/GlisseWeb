import unittest
from layout_math import compact_icon_width


class CompactRailGeometryTests(unittest.TestCase):
    def test_favicon_fits_with_scrollbar(self):
        width = compact_icon_width(62)
        self.assertEqual(width, 39)
        self.assertLessEqual(width + 2 * 4 + 8 + 2 * 2, 62)

    def test_icon_adjusts_for_a_narrow_rail(self):
        self.assertEqual(compact_icon_width(54), 34)
        self.assertLessEqual(compact_icon_width(58), compact_icon_width(62))

    def test_too_small_rail_is_rejected(self):
        with self.assertRaises(ValueError):
            compact_icon_width(30)

    def test_top_and_bottom_controls_fit(self):
        self.assertLessEqual(44 + 2 * 4, 62)


if __name__ == "__main__":
    unittest.main()
