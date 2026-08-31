"""Interactively test semantic search against the patch-note collection."""

import sys

import chromadb
from chromadb.errors import NotFoundError

from embed_chunks import (
    CHROMA_FOLDER,
    COLLECTION_NAME,
    get_embedding_function,
)


TOP_RESULTS = 3


def open_collection():
    """Open the existing OpenAI-embedded Chroma collection."""

    if not CHROMA_FOLDER.exists():
        raise FileNotFoundError(
            "Chroma database not found. Run: python embed_chunks.py"
        )

    client = chromadb.PersistentClient(
        path=str(CHROMA_FOLDER)
    )

    return client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=get_embedding_function(),
    )


def search(collection, question):
    """Retrieve and display the three chunks closest to the question."""

    result_count = min(TOP_RESULTS, collection.count())

    if result_count == 0:
        print("The collection is empty. Run: python embed_chunks.py")
        return

    # Chroma uses the collection's OpenAI embedding function to embed the
    # question, then compares that vector with the stored chunk vectors.
    results = collection.query(
        query_texts=[question],
        n_results=result_count,
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

    for index in range(result_count):
        print(f"\nResult {index + 1}")
        print(f"ID: {results['ids'][0][index]}")
        print(f"Distance: {results['distances'][0][index]:.4f}")
        print(f"Metadata: {results['metadatas'][0][index]}")
        print(results["documents"][0][index])
        print("-" * 60)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )

    try:
        collection = open_collection()
    except (FileNotFoundError, NotFoundError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print("League patch-note semantic search")
    print("Enter a question, or type 'quit' to stop.")

    while True:
        try:
            question = input("\nQuestion: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if question.lower() == "quit":
            print("Goodbye!")
            break

        if not question:
            print("Please enter a question or type 'quit'.")
            continue

        try:
            search(collection, question)
        except Exception as error:
            print(f"Search error: {error}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
