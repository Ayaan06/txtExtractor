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
