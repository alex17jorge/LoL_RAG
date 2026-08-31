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

Create a `.env` file in the project folder:

```env
OPENAI_API_KEY=your-api-key
```

The `.env` file is ignored by Git. Do not place the key directly in the Python
source or commit it. Then embed every chunk with OpenAI's
`text-embedding-3-small` model and store it in Chroma:

```powershell
python embed_chunks.py
```

After embedding, start the interactive semantic-search tester:

```powershell
python query_chroma.py
```

Enter questions at the prompt. The three closest chunks are displayed after
each question. Type `quit` to exit.

## React chatbot

The chatbot has a React frontend and a small Python API. First install the
Python and frontend packages:

```powershell
python -m pip install -r requirements.txt
cd frontend
npm install
cd ..
```

Run the API in the first terminal:

```powershell
python chat_api.py
```

Run React in a second terminal:

```powershell
cd frontend
npm run dev
```

Open the local address printed by Vite, normally `http://localhost:5173`.
Each question searches the existing Chroma database and then uses OpenAI to
write an answer. It does not embed the chunks again.

PatchBot chooses retrieval based on the question:

- Named entries such as `Yone` or `Locke` use exact metadata matching.
- Questions that name a patch load that whole patch, so the model can answer
  naturally about champions, items, runes, or systems.
- `latest`, `newest`, and `current patch` load the newest stored patch.
- Other questions use the three closest semantic-search results.

To see which patches are available, open this endpoint while the API runs:

```text
http://localhost:5000/api/patches
```

The vectors, documents, and metadata are stored in `chroma_db_openai/`. Existing
unchanged chunks are skipped on later runs to avoid unnecessary embedding API
calls.

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
