import requests
from pathlib import Path
from bs4 import BeautifulSoup
import json
import argparse
import sys

RAW_DATA_FOLDER = Path('raw_data')
SCRAPED_DATA_FOLDER = Path('processed_data/scraped')

OTHER_MODES = (
    "aram",
    "arena",
    "swarm",
    "teamfight tactics",
    "tft",
    "nexus blitz",
    "urf",
)

SKIPPED_SECTIONS = (
    "patch highlights",
    "bugfixes & qol changes",
    "updated system requirements",
    "upcoming skins & chromas",
    "related articles",
    "game systems",
    "player behavior",
    "ranked leaderboards",
    "msi cup",
)

# Intro-only sections are kept only when their heading clearly describes
# Summoner's Rift gameplay. Sections with actual entries are handled normally.
SR_OVERVIEW_KEYWORDS = (
    "summoner's rift",
    "ranked",
    "aegis",
    "apex duo",
    "objective",
    "jungle",
    "turret",
    "minion",
    "bounty",
    "bounties",
    "vision",
    "last hit",
    "gameplay",
)



def clean_text(element):
    text = element.get_text(" ", strip=True)
    return " ".join(text.split())

def download_page(url):
    """
        Take the url and send a request to the server, timeout if server does 
        not respond, check whether request succeeded and get the HTML content
    """
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text

def get_patch_name(url):
    """
        get the patch name such as "patch-26-17" from the url
    """
    if "patch-" not in url or "-notes" not in url:
        return "patch-notes"

    patch_part = url.split("patch-", 1)[1]
    patch_number = patch_part.split("-notes", 1)[0]

    return f"patch-{patch_number}"

def save_raw_html(html, url):
    """
        save the original HTML into the raw_data folder
    """
    RAW_DATA_FOLDER.mkdir(exist_ok=True)

    filename = f"{get_patch_name(url)}.html"
    path = RAW_DATA_FOLDER / filename
    path.write_text(html, encoding="utf-8")

    return path

def is_summoners_rift_section(name):
    """Keep gameplay sections unless they belong to another mode."""

    name = name.lower().strip()

    # "Classic" is a separate mode when it is the section's complete name.
    # Do not reject every use of the word because Riot may use it descriptively.
    if name == "classic" or name.startswith("league of legends classic"):
        return False

    # Reject other game modes
    for mode in OTHER_MODES:
        if mode in name:
            return False

    # Reject sections that are not useful gameplay information
    for skipped in SKIPPED_SECTIONS:
        if skipped in name:
            return False

    return True

def parse_patch_notes(html, source_url=""):
    """
        parse summoner's rift information from riot's patch notes HTML
    """
    soup = BeautifulSoup(html, "html.parser")

    container = soup.select_one("#patch-notes-container")

    if container is None:
        raise ValueError("Could not find the patch notes container")

    title_element = soup.find("h1")

    if title_element:
        title = clean_text(title_element)
    else:
        title = "League Patch Notes"

    patch = {
        "title": title,
        "source_url": source_url,
        "sections": [],
    }

    current_section = None
    current_entry = None
    current_change = None
    current_content_block = None

    elements = container.find_all(["h2", "h3", "h4", "h5", "h6", "p", "li"])

    for element in elements:
        text = clean_text(element)

        if not text:
            continue

        if element.name == "p" and element.find_parent("li"):
            continue

        if element.name == "h2":
            current_entry = None
            current_change = None
            current_content_block = None

            if is_summoners_rift_section(text):
                current_section = {
                    "name": text,
                    "intro": [],
                    "entries": [],
                }

                patch["sections"].append(current_section)

            else:
                current_section = None

            continue

        if current_section is None:
            continue

        # Riot normally puts each champion, item, or system entry in its own
        # content-border div. Reset entry state when a new card begins.
        content_block = element.find_parent("div", class_="content-border")

        if content_block is not None and content_block is not current_content_block:
            current_content_block = content_block
            current_entry = None
            current_change = None

        if element.name == "h3":
            current_entry = {
                "name": text,
                "context": [],
                "changes": [],
            }

            current_section["entries"].append(current_entry)
            current_change = None

            continue

        if element.name in ("h4", "h5", "h6"):

            if current_entry is None:
                current_entry = {
                    "name": text,
                    "context": [],
                    "changes": [],
                }

                current_section["entries"].append(current_entry)
                current_change = None
                continue

            current_change = {
                "name": text,
                "details": [],
            }

            current_entry["changes"].append(current_change)

            continue

        blockquote = element.find_parent("blockquote")

        if (
            element.name == "p"
            and blockquote
            and "context" in blockquote.get("class", [])
        ):
            if current_entry:
                current_entry["context"].append(text)
            else:
                current_section["intro"].append(text)

            continue

        if current_entry is None:
            current_section["intro"].append(text)
            continue

        if current_change is None:
            current_change = {
                "name": None,
                "details": [],
            }

            current_entry["changes"].append(current_change)

        current_change["details"].append(text)

    # Remove empty headings and fail loudly if Riot changes the page structure.
    for section in patch["sections"]:
        section["entries"] = [
            entry
            for entry in section["entries"]
            if entry["context"] or entry["changes"]
        ]

    patch["sections"] = [
        section
        for section in patch["sections"]
        if section["entries"]
        or (
            section["intro"]
            and any(
                keyword in section["name"].lower()
                for keyword in SR_OVERVIEW_KEYWORDS
            )
        )
    ]

    if not patch["sections"]:
        raise ValueError("No Summoner's Rift sections were found")

    return patch

def save_json(data, url):
    """
        Save processed patch data as JSON
    """
    SCRAPED_DATA_FOLDER.mkdir(parents=True, exist_ok=True)

    filename = f"{get_patch_name(url)}.json"
    path = SCRAPED_DATA_FOLDER / filename

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    return path

def scrape_patch_notes(url):
    """
        download, save and parse a riot patch notes page
    """
    html = download_page(url)

    save_raw_html(html, url)

    patch_data = parse_patch_notes(html, url)

    return patch_data

def main():
    """
        run the patch notse scraper from the command line
    """
    parser = argparse.ArgumentParser(
        description="scrape summoner's rift patch notes"
    )

    parser.add_argument(
        "url",
        help="official riot patch notes url"
    )

    args = parser.parse_args()

    try: 
        patch_data = scrape_patch_notes(args.url)
        json_path = save_json(patch_data, args.url)

    except requests.RequestException as error:
        print(f"Download error: {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"parsing error: {error}", file=sys.stderr)
        return 1

    print(f"patch notes saved to: {json_path}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
