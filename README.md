# txtExtractor

`txtExtractor` is a simple command-line tool that searches Markdown (`.md`) or
plain-text (`.txt`) files for user-specified keywords and writes a clean,
organized table of matches to a `.txt` file next to the source file.

## File Extractor (local .md/.txt)

1. Run the script:

   ```bash
   python extractor.py
   ```

2. When prompted, provide the path to the `.txt` or `.md` file you want to
   search.
3. Enter one or more keywords separated by commas. The search is
   case-insensitive.

The saved results are clean tables with four columns:

Company	Role	Location	Link

Only entries that match your keywords are included. Common Markdown formatting
is stripped from the values (links, images, inline code, HTML tags).

Outputs
- Pretty-aligned text for easy reading:
  - `<input_stem>_extracted.txt` (fixed-width columns, capped with ellipsis)
- TSV (tabs) for data interchange:
  - `<input_stem>_extracted.tsv`
- CSV with RFC 4180 quoting:
  - `<input_stem>_extracted.csv` (best for Excel/Sheets)

Note: This tool only reads a local `.md`/`.txt` file. For scraping Eluta.ca, use the separate tool below.

## Eluta.ca Scraper (separate tool)

Fetch job listings directly from Eluta.ca and export in the same formats.

Usage
- Run: `python eluta_cli.py`
- Enter keywords (e.g., `software engineer`), optional location (e.g., `Toronto, ON`), and the number of pages to fetch.
- Optionally filter out results with dead links (quick HTTP check).

Outputs
- Saved in the working directory as `eluta_<keywords>_extracted.*` with `.txt`/`.tsv`/`.csv`/`.md` variants.

Notes
- Respect Eluta.ca’s Terms of Service and robots.txt.
- Network access is required. If you’re behind a proxy or VPN and see TLS/SSL errors, configure `HTTPS_PROXY`/`HTTP_PROXY` env vars or run without the dead-link filter.
- If Eluta changes their HTML, update `eluta_scraper.py`.
