# txtExtractor

`txtExtractor` is a simple command-line tool that searches Markdown (`.md`) or
plain-text (`.txt`) files for user-specified keywords and writes a clean,
organized table of matches to a `.txt` file next to the source file.

## Usage

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

Optional: Eluta.ca integration
- During the run, you can opt-in to also fetch matching jobs from Eluta.ca using the same keywords. You can provide an optional location (e.g., `Toronto, ON`) and number of pages to fetch.
- The external jobs are merged with deduplication before writing outputs.

## Eluta.ca scraper (optional)

You can fetch job listings directly from Eluta.ca and export them in the same
formats as above.

Usage
- Run: `python eluta_cli.py`
- Enter keywords (e.g., `software engineer`), optional location (e.g., `Toronto, ON`), and the number of pages to fetch.
- Optionally filter out results with dead links (quick HTTP check).

Outputs
- Saved in the working directory as `eluta_<keywords>_extracted.*` with the same `.txt`/`.tsv`/`.csv`/`.md` variants.

Notes
- Be mindful of Eluta.ca’s Terms of Service and robots.txt when scraping.
- HTML structures can change; if parsing breaks, update `eluta_scraper.py`.
- Network access is required; behind strict networks the fetch may not work.
