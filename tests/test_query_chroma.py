import unittest
from unittest.mock import patch

from query_chroma import main, search


class FakeCollection:
    def count(self):
        return 1

    def query(self, query_texts, n_results, include):
        return {
            "ids": [["26.17-champions-aurelion-sol"]],
            "distances": [[0.1]],
            "metadatas": [[{"patch": "26.17"}]],
            "documents": [["Aurelion Sol patch changes"]],
        }


class InteractiveQueryTests(unittest.TestCase):
    def test_search_requests_top_results(self):
        search(FakeCollection(), "What changed for Aurelion Sol?")

    @patch("query_chroma.open_collection", return_value=FakeCollection())
    @patch("builtins.input", return_value="quit")
    def test_quit_stops_the_loop(self, input_mock, collection_mock):
        self.assertEqual(main(), 0)
        input_mock.assert_called_once()
        collection_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
