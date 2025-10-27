# txtExtractor

`txtExtractor` is a simple command-line tool that searches Markdown (`.md`) or
plain-text (`.txt`) files for user-specified keywords and prints the sentences
that contain them.

## Usage

1. Run the script:

   ```bash
   python extractor.py
   ```

2. When prompted, provide the path to the `.txt` or `.md` file you want to
   search.
3. Enter one or more keywords separated by commas. The search is
   case-insensitive.

The tool will list each keyword alongside the sentences where it appears. If a
keyword does not appear in the file, the script will let you know.
