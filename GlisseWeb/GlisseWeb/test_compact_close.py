"""Contrôle du placement du × dans la petite barre à favicons."""
import unittest
from layout_math import compact_icon_width, compact_close_geometry


class CompactCloseGeometryTests(unittest.TestCase):
    def test_close_fits_in_regular_rail(self):
        width = compact_icon_width(62)
        x, y, size = compact_close_geometry(width, 41)
        self.assertEqual((x, y, size), (23, 1, 15))
        self.assertLessEqual(x + size, width)
        self.assertLessEqual(y + size, 41)

    def test_close_fits_with_smaller_rail(self):
        for rail_width in (50, 54, 58, 62):
            width = compact_icon_width(rail_width)
            x, y, size = compact_close_geometry(width, 41)
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(x + size, width)
            self.assertLessEqual(y + size, 41)

    def test_close_stays_at_top_right(self):
        for width in (30, 39, 47):
            x, y, size = compact_close_geometry(width, 41)
            self.assertEqual(x + size, width - 1)
            self.assertEqual(y, 1)

    def test_rejects_too_small_card(self):
        with self.assertRaises(ValueError):
            compact_close_geometry(15, 41)
        with self.assertRaises(ValueError):
            compact_close_geometry(39, 15)


if __name__ == "__main__":
    unittest.main()
