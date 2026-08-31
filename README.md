# League of Legends Summoner's Rift Patch Scraper

Scrapes gameplay changes from Riot's official League of Legends patch notes and
outputs only modern **Summoner's Rift** sections such as Champions, Items, Runes,
Systems, ranked changes, and other Rift mechanics. Alternate modes such as
Classic, ARAM, Arena, Swarm, and TFT are excluded.

## Setup

```powershell
python -m pip install -r requirements.txt
```

## Usage

Download and process a patch:

```powershell
python lol_patch_scraper.py "https://www.leagueoflegends.com/en-us/news/game-updates/league-of-legends-patch-26-17-notes/"
```

Then create the chunks:

```powershell
python chunk_patch_notes.py processed_data/scraped/patch-26-17.json
```

The pipeline uses three locations:

```text
raw_data/patch-26-17.html                  Original Riot webpage
processed_data/scraped/patch-26-17.json   Parsed Summoner's Rift data
processed_data/chunks/patch-26-17.jsonl   RAG chunks
```

Example text shape:

```text
Champions:
  Aurelion Sol:
    Q - Breath of Light:
      - Mana Cost Per Second: 35 / 40 / 45 / 50 / 55 ⇒ 30 / 35 / 40 / 45 / 50

Items:
  Stormrazor:
    - Attack Speed: 20% ⇒ 25%
```

The scraper anchors on Riot's semantic `#patch-notes-container` and section
headings instead of generated CSS class names. Catch-all bugfix/QoL sections are
excluded because Riot mixes changes for multiple modes there.

## Tests

```powershell
python -m unittest discover -s tests -v
```
