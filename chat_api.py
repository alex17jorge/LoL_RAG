"""HTTP API for PatchBot."""

import os
import re

from flask import Flask, jsonify, request
from openai import OpenAI

from query_chroma import TOP_RESULTS, open_collection


CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
MAX_QUESTION_LENGTH = 1000
MAX_HISTORY_MESSAGES = 6
MAX_HISTORY_MESSAGE_LENGTH = 2000
PATCH_PATTERN = re.compile(r"\b\d+\.\d+\b")

ANSWER_INSTRUCTIONS = """
You are The Herald. Answer questions about League of Legends Summoner's Rift
patch notes using only the supplied context.

- Never invent a change. Say when the context does not contain the answer.
- Use conversation history only to understand follow-up questions. Patch-note
  facts must come from the supplied context.
- Mention patch numbers when available.
- For lists and summaries, inspect every supplied chunk.
- Discuss only the champion, item, rune, system, or category being asked about.
- Classify changes by gameplay effect, not just numerical direction.
- Lower cooldowns, costs, and penalties are usually buffs.
- A penalty changing from -10% to -5% is a buff, not a nerf.
- Patch notes do not prove current meta strength. Only call something strong or
  weak when the supplied notes explicitly say so.
- Be concise. Use bullets when listing multiple changes.
"""

app = Flask(__name__)


def patch_number(patch):
    """Convert '26.17' into (26, 17) so patches sort correctly."""

    return tuple(int(part) for part in patch.split("."))


def patch_in_question(question):
    """Return an explicit patch number, if the question contains one."""

    match = PATCH_PATTERN.search(question)
    return match.group() if match else None


def asks_for_latest(question):
    """Return whether the question asks for the newest stored patch."""

    lower_question = question.lower()
    latest_words = ("latest", "newest", "current patch", "new patch")
    return any(word in lower_question for word in latest_words)


def load_records(collection):
    """Load all documents and metadata from Chroma."""

    return collection.get(include=["documents", "metadatas"])


def clean_history(history):
    """Keep a small, safe list of previous user and assistant messages."""

    if not isinstance(history, list):
        return []

    cleaned = []

    for message in history[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(message, dict):
            continue

        role = message.get("role")
        content = message.get("content")

        if role not in ("user", "assistant") or not isinstance(content, str):
            continue

        content = content.strip()[:MAX_HISTORY_MESSAGE_LENGTH]

        if content:
            cleaned.append({"role": role, "content": content})

    return cleaned


def latest_patch(records):
    """Return the newest patch found in the local database."""

    patches = {
        str(metadata.get("patch"))
        for metadata in records["metadatas"]
        if PATCH_PATTERN.fullmatch(str(metadata.get("patch", "")))
    }

    return max(patches, key=patch_number) if patches else None


def find_entry(records, question):
    """Find an exact stored champion, item, rune, or system name."""

    lower_question = question.lower()
    names = {
        str(metadata["entry"])
        for metadata in records["metadatas"]
        if metadata.get("entry")
    }

    # Longest first prevents a shorter name from winning accidentally.
    for name in sorted(names, key=len, reverse=True):
        pattern = rf"(?<!\w){re.escape(name.lower())}(?!\w)"

        if re.search(pattern, lower_question):
            return name

    return None


def matching_chunks(records, patch=None, entry=None):
    """Filter stored chunks by exact patch and/or exact entry metadata."""

    chunks = []

    for document, metadata in zip(
        records["documents"],
        records["metadatas"],
    ):
        if patch and str(metadata.get("patch")) != patch:
            continue

        if entry and str(metadata.get("entry", "")).casefold() != entry.casefold():
            continue

        chunks.append({
            "content": document,
            "metadata": metadata,
        })

    return chunks


def semantic_search(collection, question):
    """Return the closest chunks when no patch or entry is known."""

    result_count = min(TOP_RESULTS, collection.count())

    if result_count == 0:
        return []

    results = collection.query(
        query_texts=[question],
        n_results=result_count,
        include=["documents", "metadatas"],
    )

    return [
        {"content": document, "metadata": metadata}
        for document, metadata in zip(
            results["documents"][0],
            results["metadatas"][0],
        )
    ]


def retrieve_chunks(collection, question, history=None):
    """Retrieve by exact entry, whole patch, or semantic similarity."""

    records = load_records(collection)
    patch = patch_in_question(question)

    if patch is None and asks_for_latest(question):
        patch = latest_patch(records)

    entry = find_entry(records, question)

    # If the new question is vague, look backward for its subject and patch.
    for message in reversed(history or []):
        previous_text = message["content"]

        if patch is None:
            patch = patch_in_question(previous_text)
            if patch is None and asks_for_latest(previous_text):
                patch = latest_patch(records)

        if entry is None:
            entry = find_entry(records, previous_text)

        if patch and entry:
            break

    # Exact metadata avoids collisions such as Locke versus Locket.
    if entry:
        return matching_chunks(records, patch=patch, entry=entry), patch

    # Whole-patch context handles summaries and arbitrary question wording.
    if patch:
        return matching_chunks(records, patch=patch), patch

    search_text = "\n".join(
        [message["content"] for message in (history or [])] + [question]
    )
    return semantic_search(collection, search_text), None


def answer_question(question, chunks, patch_used=None, history=None):
    """Ask OpenAI to answer from the retrieved chunks."""

    context = "\n\n--- PATCH NOTE ---\n\n".join(
        chunk["content"] for chunk in chunks
    )

    if patch_used:
        question += f"\n\nRetrieved patch: {patch_used}."

    current_message = f"Question:\n{question}\n\nPatch-note context:\n{context}"
    input_messages = list(history or [])
    input_messages.append({"role": "user", "content": current_message})

    response = OpenAI().responses.create(
        model=CHAT_MODEL,
        instructions=ANSWER_INSTRUCTIONS,
        input=input_messages,
        store=False,
    )

    return response.output_text


def official_patch_url(patch, stored_url):
    """Return an official Riot patch-notes link."""

    if str(stored_url).startswith("https://www.leagueoflegends.com/"):
        return stored_url

    slug = patch.replace(".", "-")
    return (
        "https://www.leagueoflegends.com/en-us/news/game-updates/"
        f"league-of-legends-patch-{slug}-notes/"
    )


def make_sources(chunks, answer):
    """Return one official source for each patch used in the answer."""

    mentioned = set(PATCH_PATTERN.findall(answer))
    sources = {}

    for chunk in chunks:
        metadata = chunk["metadata"]
        patch = str(metadata.get("patch", ""))

        if not PATCH_PATTERN.fullmatch(patch):
            continue

        if mentioned and patch not in mentioned:
            continue

        sources[patch] = {
            "patch": patch,
            "url": official_patch_url(patch, metadata.get("source_url", "")),
        }

    return sorted(sources.values(), key=lambda source: patch_number(source["patch"]))


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/patches")
def patches():
    """List patches available in the local database."""

    try:
        records = load_records(open_collection())
        found = sorted({
            str(metadata.get("patch"))
            for metadata in records["metadatas"]
            if PATCH_PATTERN.fullmatch(str(metadata.get("patch", "")))
        }, key=patch_number)

        return jsonify({
            "patches_with_data": found,
            "latest": found[-1] if found else None,
        })
    except Exception:
        app.logger.exception("Could not list stored patches")
        return jsonify({"error": "Could not read the patch database."}), 500


@app.post("/api/chat")
def chat():
    """Answer one PatchBot question."""

    data = request.get_json(silent=True) or {}
    question = str(data.get("question", "")).strip()
    history = clean_history(data.get("history"))

    if not question:
        return jsonify({"error": "Please enter a question."}), 400

    if len(question) > MAX_QUESTION_LENGTH:
        return jsonify({
            "error": f"Question must be {MAX_QUESTION_LENGTH} characters or fewer."
        }), 400

    try:
        chunks, patch_used = retrieve_chunks(
            open_collection(),
            question,
            history,
        )

        if not chunks:
            answer = (
                f"I do not have data for patch {patch_used}."
                if patch_used
                else "I could not find relevant patch-note data."
            )
            return jsonify({
                "answer": answer,
                "sources": [],
                "data_through_patch": patch_used,
            })

        answer = answer_question(question, chunks, patch_used, history)

        return jsonify({
            "answer": answer,
            "sources": make_sources(chunks, answer),
            "data_through_patch": patch_used,
        })
    except Exception:
        app.logger.exception("PatchBot request failed")
        return jsonify({"error": "PatchBot could not answer that question."}), 500


if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG") == "1",
        port=5000,
    )
