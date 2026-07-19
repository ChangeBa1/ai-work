import base64
import urllib.parse
import unittest

from top_report_scraper.api import encode_parameter, matches_person, normalize_week


class ApiHelpersTest(unittest.TestCase):
    def test_parameter_encoding_matches_browser(self):
        encoded = encode_parameter("2026_24")
        decoded = base64.b64decode(encoded).decode()
        self.assertEqual(urllib.parse.unquote(decoded), "2026_24")

    def test_normalize_week(self):
        self.assertEqual(normalize_week("2026-7"), "2026_07")
        self.assertEqual(normalize_week("202630"), "2026_30")

    def test_person_matches_code_or_name(self):
        row = {"code": "123456", "name": "山田 太郎"}
        self.assertTrue(matches_person(row, ["123456"]))
        self.assertTrue(matches_person(row, ["山田"]))
        self.assertFalse(matches_person(row, ["佐藤"]))


if __name__ == "__main__":
    unittest.main()

