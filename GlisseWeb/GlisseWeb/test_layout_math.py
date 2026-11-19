import unittest
from layout_math import sidebar_grid, card_preview_height


class SidebarGridTests(unittest.TestCase):
    def test_one_column_then_two(self):
        self.assertEqual(sidebar_grid(1, 390)[0], 1)
        self.assertEqual(sidebar_grid(3, 390)[0], 1)
        self.assertEqual(sidebar_grid(4, 390)[0], 2)
        self.assertEqual(sidebar_grid(25, 390)[0], 2)

    def test_fit_ten_in_five_rows_typical_windows(self):
        for height in (520, 600, 720, 860):
            cols, width, card_h = sidebar_grid(10, 388, viewport_height=height)
            self.assertEqual(cols, 2)
            self.assertGreater(width, 140)
            self.assertLessEqual(card_h * 5 + 6 * 4, height)

    def test_cards_fit_horizontally(self):
        for viewport in range(240, 410, 5):
            for n in range(1, 65):
                cols, width, height = sidebar_grid(n, viewport, viewport_height=600)
                self.assertLessEqual(cols * width + 6 * (cols - 1), viewport)
                self.assertGreaterEqual(height, 80)

    def test_small_window_keeps_readable_buttons(self):
        cols, width, height = sidebar_grid(40, 244, viewport_height=270)
        self.assertEqual(cols, 1)
        self.assertGreaterEqual(height, 80)
        self.assertLess(width, 244)

    def test_card_contents_not_clipped(self):
        for h in range(80, 220):
            thumb = card_preview_height(h, 5, 22, 4)
            self.assertLessEqual(thumb + 5 * 2 + 22 + 4 + 2, h)
            self.assertGreaterEqual(thumb, 32)

    def test_height_never_grows_with_more_tabs(self):
        heights = [sidebar_grid(n,388,viewport_height=620)[2] for n in range(1, 55)]
        self.assertEqual(heights,sorted(heights,reverse=True))


if __name__ == '__main__':
    unittest.main()
