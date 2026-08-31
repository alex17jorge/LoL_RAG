import os
import unittest
from unittest.mock import patch

from embed_chunks import (
    find_chunks_to_upsert,
    get_embedding_function,
    store_chunks,
)


class FakeCollection:
    """Small stand-in for Chroma so unit tests do not load an embedding model."""

    def __init__(self):
        self.calls = []

    def upsert(self, ids, documents, metadatas):
        self.calls.append(
            {
                "ids": ids,
                "documents": documents,
                "metadatas": metadatas,
            }
        )


class FakeLookupCollection:
    def get(self, ids, include):
        return {
            "ids": [ids[0]],
            "documents": ["unchanged content"],
        }


class EmbeddingPipelineTests(unittest.TestCase):
    def test_missing_openai_key_has_clear_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
                get_embedding_function()

    def test_only_new_or_changed_chunks_are_embedded(self):
        chunks = [
            {"id": "existing", "content": "unchanged content", "metadata": {}},
            {"id": "new", "content": "new content", "metadata": {}},
        ]

        result = find_chunks_to_upsert(FakeLookupCollection(), chunks)

        self.assertEqual(result, [chunks[1]])

    def test_store_chunks_sends_content_and_metadata_to_chroma(self):
        chunks = [
            {
                "id": "26.17-champions-aurelion-sol",
                "content": "Patch: 26.17\nEntry: Aurelion Sol",
                "metadata": {
                    "patch": "26.17",
                    "section": "Champions",
                    "entry": "Aurelion Sol",
                },
            }
        ]
        collection = FakeCollection()

        store_chunks(collection, chunks)

        self.assertEqual(collection.calls[0]["ids"], [chunks[0]["id"]])
        self.assertEqual(collection.calls[0]["documents"], [chunks[0]["content"]])
        self.assertEqual(collection.calls[0]["metadatas"], [chunks[0]["metadata"]])


if __name__ == "__main__":
    unittest.main()
