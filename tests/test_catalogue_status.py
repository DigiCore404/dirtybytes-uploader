from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from utils.catalogue_browser import empty_search_page,http_error

class CatalogueStatusTests(unittest.TestCase):
    def test_only_confirmed_jeedoo_empty_search_is_not_an_error(self):
        query='https://www.jeedoo.com/stream-download/?search=Example+10'
        headings=['No results for “Example 10”']
        self.assertTrue(empty_search_page(404,query,headings))
        for status,url,titles in [(403,query,headings),(200,query,headings),(404,query,['Page not found']),(404,'https://www.jeedoo.com/product/123-Example/',headings),(404,'https://www.jeedoo.com/',headings),(404,'https://example.com/?search=Example',headings)]:
            with self.subTest(status=status,url=url,titles=titles):self.assertFalse(empty_search_page(status,url,titles))
    def test_errors_distinguish_missing_page_access_and_rate_limit(self):
        self.assertIn('not found',http_error(404))
        self.assertNotIn('block',http_error(404))
        self.assertIn('refused access',http_error(403))
        self.assertIn('limiting requests',http_error(429))
        self.assertIn('HTTP 503',http_error(503))

if __name__=='__main__':unittest.main()
