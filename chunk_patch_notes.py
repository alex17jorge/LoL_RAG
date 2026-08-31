import argparse 
import json
import re
from pathlib import Path

CHUNKS_FOLDER = Path("processed_data/chunks")

def load_patch(file_path):
    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)

def get_patch_number(patch_data, file_path):
    title = patch_data.get("title", "")
    match = re.search(r"\d+\.\d+", title)

    if match:
        return match.group()

    return file_path.stem.replace("patch-", "").replace("-", ".")


def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)

    return text.strip("-")

def build_entry_content(patch_number, section_name, entry):
    lines = [
        f"Patch: {patch_number}",
        f"Section: {section_name}",
        f"Entry: {entry['name']}",
    ]

    context = entry.get("context", [])

    if context: 
        lines.append("")
        lines.append("Context:")
        lines.extend(context)

    for change in entry.get("changes", []):
        if change.get("name"):
            lines.append("")
            lines.append(change["name"])

        for detail in change.get("details", []):
            lines.append(f"- {detail}")

    return "\n".join(lines)

def build_intro_content(patch_number, section_name, intro):
    lines = [
        f"Patch: {patch_number}",
        f"Section: {section_name}",
        "",
        "Overview:",
    ]

    lines.extend(intro)
    return "\n".join(lines)



def create_chunks(patch_data, file_path):
    """Create chunks from the structured patch data."""

    chunks = []

    patch_number = get_patch_number(patch_data, file_path)
    source_url = patch_data.get("source_url", "")

    for section in patch_data.get("sections", []):

        section_name = section["name"]
        section_id = slugify(section_name)

        # Create section overview chunk
        intro = section.get("intro", [])

        if intro:
            chunks.append({
                "id": f"{patch_number}-{section_id}-overview",

                "content": build_intro_content(
                    patch_number,
                    section_name,
                    intro,
                ),

                "metadata": {
                    "patch": patch_number,
                    "section": section_name,
                    "entry": None,
                    "source_url": source_url,
                    "chunk_type": "section_overview",
                },
            })

        # Create one chunk for every entry
        for entry in section.get("entries", []):

            entry_name = entry["name"]
            entry_id = slugify(entry_name)

            chunks.append({
                "id": f"{patch_number}-{section_id}-{entry_id}",

                "content": build_entry_content(
                    patch_number,
                    section_name,
                    entry,
                ),

                "metadata": {
                    "patch": patch_number,
                    "section": section_name,
                    "entry": entry_name,
                    "source_url": source_url,
                    "chunk_type": "entry",
                },
            })

    return chunks


def save_chunks(chunks, input_path):
    """Save chunks as a JSONL file."""

    CHUNKS_FOLDER.mkdir(parents=True, exist_ok=True)

    output_path = CHUNKS_FOLDER / f"{input_path.stem}.jsonl"

    with output_path.open("w", encoding="utf-8") as file:

        for chunk in chunks:
            file.write(
                json.dumps(chunk, ensure_ascii=False) + "\n"
            )

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Create chunks from League patch notes"
    )

    parser.add_argument(
        "input_file",
        type=Path,
        help="Processed patch JSON file",
    )

    args = parser.parse_args()

    try:
        patch_data = load_patch(args.input_file)

        chunks = create_chunks(
            patch_data,
            args.input_file,
        )

        output_path = save_chunks(
            chunks,
            args.input_file,
        )

    except FileNotFoundError:
        print(f"File not found: {args.input_file}")
        return 1

    except json.JSONDecodeError:
        print(f"Invalid JSON: {args.input_file}")
        return 1

    print(f"Created {len(chunks)} chunks")
    print(f"Saved to: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
