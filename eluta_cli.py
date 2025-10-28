from pathlib import Path
from typing import List

from eluta_scraper import jobs_to_rows, search_eluta

# Reuse formatting and link-check utilities from extractor
from extractor import (
    _filter_rows_by_live_links,  # type: ignore
    _format_csv,  # type: ignore
    _format_markdown_table,  # type: ignore
    _format_pretty_table,  # type: ignore
    _format_tsv,  # type: ignore
    prompt_yes_no,  # type: ignore
)


def prompt(text: str, default: str = "") -> str:
    s = input(text).strip()
    if not s:
        return default
    return s


def main() -> None:
    print("Eluta.ca scraper")
    query = prompt("Enter search keywords (e.g. 'software engineer'): ")
    location = prompt("Enter location (e.g. 'Toronto, ON') [optional]: ")
    pages_raw = prompt("How many pages to fetch? [1]: ", default="1")
    try:
        pages = max(1, int(pages_raw))
    except ValueError:
        pages = 1

    jobs = search_eluta(query=query, location=location, pages=pages)
    rows: List[tuple[str, str, str, str]] = jobs_to_rows(jobs)

    if rows and prompt_yes_no("Filter out jobs with dead links?", default=False):
        rows = _filter_rows_by_live_links(rows)

    # Render
    tsv_text = _format_tsv(rows)
    csv_text = _format_csv(rows)
    pretty_text = _format_pretty_table(rows)
    md_text = _format_markdown_table(rows)

    # Preview
    preview_lines = pretty_text.splitlines()
    preview = "\n".join(preview_lines[: min(6, len(preview_lines))])
    print("\n" + preview)

    # Save files
    safe_q = "_".join(query.split()) or "results"
    base = Path(f"eluta_{safe_q}_extracted")
    paths = {
        "txt": base.with_suffix(".txt"),
        "tsv": base.with_suffix(".tsv"),
        "csv": base.with_suffix(".csv"),
        "md": base.with_suffix(".md"),
    }
    try:
        paths["txt"].write_text(pretty_text, encoding="utf-8")
        paths["tsv"].write_text(tsv_text, encoding="utf-8")
        paths["csv"].write_text(csv_text, encoding="utf-8")
        paths["md"].write_text(md_text, encoding="utf-8")
        print(f"Saved: {paths['txt']}")
        print(f"Saved: {paths['tsv']}")
        print(f"Saved: {paths['csv']}")
        print(f"Saved: {paths['md']}")
    except OSError as exc:
        print(f"Failed to write outputs: {exc}")


if __name__ == "__main__":
    main()

