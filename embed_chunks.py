"""Embed League patch-note chunks and store them in Chroma."""

import argparse
import json
import os
import sys
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv


CHUNKS_FOLDER = Path("processed_data/chunks")
CHROMA_FOLDER = Path("chroma_db_openai")

COLLECTION_NAME = "lol_patch_notes_openai"
EMBEDDING_MODEL = "text-embedding-3-small"

BATCH_SIZE = 100


# Load OPENAI_API_KEY from the project's .env file. Existing environment
# variables take priority because load_dotenv does not override them by default.
load_dotenv(Path(__file__).resolve().parent / ".env")


def find_chunk_files(input_path):
    """Find JSONL chunk files."""

    if input_path.is_file():
        return [input_path]

    if input_path.is_dir():
        return sorted(input_path.glob("*.jsonl"))

    raise FileNotFoundError(f"Chunk path not found: {input_path}")


def load_chunks(input_path):
    """Load chunks from JSONL files."""

    chunks = []
    chunk_files = find_chunk_files(input_path)

    if not chunk_files:
        raise ValueError(f"No JSONL files found in: {input_path}")

    for file_path in chunk_files:

        with file_path.open("r", encoding="utf-8") as file:

            for line_number, line in enumerate(file, start=1):

                if not line.strip():
                    continue

                try:
                    chunk = json.loads(line)

                except json.JSONDecodeError:
                    raise ValueError(
                        f"Invalid JSON in {file_path} "
                        f"on line {line_number}"
                    )

                if not chunk.get("id"):
                    raise ValueError(
                        f"Missing chunk ID in {file_path}"
                    )

                if not chunk.get("content"):
                    raise ValueError(
                        f"Missing chunk content in {file_path}"
                    )

                metadata = chunk.get("metadata", {})

                # Chroma cannot store None as metadata.
                clean_metadata = {}

                for key, value in metadata.items():
                    if value is not None:
                        clean_metadata[key] = value

                clean_metadata["chunk_file"] = file_path.name

                chunks.append({
                    "id": str(chunk["id"]),
                    "content": str(chunk["content"]),
                    "metadata": clean_metadata,
                })

    return chunks


def get_embedding_function():
    """Create the OpenAI embedding model."""

    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError(
            "OPENAI_API_KEY environment variable is not set."
        )

    return OpenAIEmbeddingFunction(
        api_key_env_var="OPENAI_API_KEY",
        model_name=EMBEDDING_MODEL,
    )


def get_collection():
    """Open Chroma and create the patch-note collection."""

    CHROMA_FOLDER.mkdir(exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(CHROMA_FOLDER)
    )

    embedding_function = get_embedding_function()

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata={
            "description": "Summoner's Rift patch notes",
            "embedding_model": EMBEDDING_MODEL,
        },
    )

    return collection


def find_chunks_to_upsert(collection, chunks):
    """Return only new or changed chunks to avoid unnecessary API charges."""

    stored_documents = {}

    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start:start + BATCH_SIZE]
        chunk_ids = [chunk["id"] for chunk in batch]

        existing = collection.get(
            ids=chunk_ids,
            include=["documents"],
        )

        for chunk_id, document in zip(
            existing["ids"],
            existing["documents"],
        ):
            stored_documents[chunk_id] = document

    return [
        chunk
        for chunk in chunks
        if stored_documents.get(chunk["id"]) != chunk["content"]
    ]


def store_chunks(collection, chunks):
    """Store chunks in batches."""

    for start in range(0, len(chunks), BATCH_SIZE):

        batch = chunks[start:start + BATCH_SIZE]

        ids = []
        documents = []
        metadatas = []

        for chunk in batch:
            ids.append(chunk["id"])
            documents.append(chunk["content"])
            metadatas.append(chunk["metadata"])

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )


def main():

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(
            encoding="utf-8",
            errors="replace",
        )

    parser = argparse.ArgumentParser(
        description="Embed League patch-note chunks"
    )

    parser.add_argument(
        "input_path",
        nargs="?",
        type=Path,
        default=CHUNKS_FOLDER,
        help="JSONL file or folder",
    )

    args = parser.parse_args()

    try:

        chunks = load_chunks(args.input_path)

        collection = get_collection()

        chunks_to_upsert = find_chunks_to_upsert(
            collection,
            chunks,
        )

        store_chunks(
            collection,
            chunks_to_upsert,
        )

    except (
        FileNotFoundError,
        ValueError,
    ) as error:

        print(
            f"Error: {error}",
            file=sys.stderr,
        )

        return 1

    print(f"Loaded {len(chunks)} chunks")

    print(
        f"Embedded {len(chunks_to_upsert)} new or changed chunks"
    )

    print(
        f"Skipped {len(chunks) - len(chunks_to_upsert)} unchanged chunks"
    )

    print(
        f"Collection contains "
        f"{collection.count()} records"
    )

    print(
        f"Embedding model: {EMBEDDING_MODEL}"
    )

    print(
        f"Chroma database: {CHROMA_FOLDER}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
