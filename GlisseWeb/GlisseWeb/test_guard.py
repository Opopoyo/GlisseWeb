import unittest
from guard import query_to_url, is_allowed_main_url, suspicious_download


class GuardTests(unittest.TestCase):
    def test_search(self):
        self.assertEqual(query_to_url('robot aspirateur'), 'https://www.google.com/search?q=robot+aspirateur')
        self.assertEqual(query_to_url(''), 'https://www.google.com/')
        self.assertEqual(query_to_url('javascript:alert(1)').split('?')[0], 'https://www.google.com/search')

    def test_web_addresses(self):
        self.assertEqual(query_to_url('example.org'), 'https://example.org')
        self.assertEqual(query_to_url('http://example.com'), 'http://example.com')
        self.assertEqual(query_to_url('localhost:8080'), 'http://localhost:8080')
        self.assertIn('google.com/search?', query_to_url('google.com@evil.example'))

    def test_navigation(self):
        for url in ('file:///C:/secret.txt', 'javascript:alert(1)',
                    'data:text/html,hi', 'chrome://settings', 'ftp://host/x',
                    'mailto:a@b.com'):
            with self.subTest(url=url):
                self.assertFalse(is_allowed_main_url(url))
        for url in ('https://example.com', 'http://localhost:9000', 'about:blank'):
            self.assertTrue(is_allowed_main_url(url))

    def test_download_extensions(self):
        for name in ('setup.exe', 'report.pdf.exe', 'run.PS1', 'dir\\bad.lnk', 'app.MSIX'):
            self.assertTrue(suspicious_download(name))
        for name in ('document.pdf', 'photo.jpg', 'test.zip', 'note.txt'):
            self.assertFalse(suspicious_download(name))


if __name__ == '__main__':
    unittest.main()
