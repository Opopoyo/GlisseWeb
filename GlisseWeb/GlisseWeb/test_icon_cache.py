import unittest
from pathlib import Path
from icon_cache import favicon_path


class CacheTests(unittest.TestCase):
    def test_same_domain_same_icon(self):
        folder = Path('Favicons')
        self.assertEqual(favicon_path(folder,'https://example.org/a'),
                         favicon_path(folder,'https://example.org/b?q=1'))
        self.assertEqual(favicon_path(folder,'http://EXAMPLE.ORG/'),
                         favicon_path(folder,'https://example.org/'))

    def test_not_injected_path(self):
        folder = Path('Favicons')
        for url in ('file:///C:/foo', 'data:text/html,abc', 'about:blank',
                    'javascript:alert(1)', 'ftp://example.org', ''):
            self.assertIsNone(favicon_path(folder, url))
        actual = favicon_path(folder,'https://example.org/../../windows/hosts')
        self.assertEqual(actual.parent, folder)
        self.assertEqual(len(actual.stem),64)

    def test_invalid_urls(self):
        folder = Path('Favicons')
        self.assertIsNone(favicon_path(folder, 'https://[badhost]/'))


if __name__ == '__main__':
    unittest.main()
