import re
import html
from pathlib import Path
from urllib import request, error
from concurrent.futures import ThreadPoolExecutor, as_completed

SUPPORTED_EXTENSIONS = {".txt", ".md"}


def prompt_file_path() -> Path:
    """Prompt the user to supply a path to a supported text file."""
    while True:
        raw_path = input("Enter the path to a .txt or .md file: ").strip().strip('"')
        if not raw_path:
            print("Please provide a non-empty path.")
            continue

        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            print(f"No file found at {path}. Try again.")
            continue

        if not path.is_file():
            print(f"{path} is not a file. Try again.")
            continue

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            supported = ', '.join(sorted(SUPPORTED_EXTENSIONS))
            print(f"Unsupported file type: {path.suffix}. Supported types are: {supported}.")
            continue

        return path


def prompt_keywords() -> list[str]:
    """Prompt the user to supply one or more keywords."""
    while True:
        raw_keywords = input("Enter keywords to search for (comma separated): ")
        keywords = [kw.strip() for kw in raw_keywords.split(',') if kw.strip()]
        if not keywords:
            print("Please enter at least one keyword.")
            continue
        return keywords


def prompt_yes_no(question: str, default: bool = False) -> bool:
    prompt = " [Y/n]: " if default else " [y/N]: "
    while True:
        ans = input(question + prompt).strip().lower()
        if not ans:
            return default
        if ans in {"y", "yes"}:
            return True
        if ans in {"n", "no"}:
            return False
        print("Please answer 'y' or 'n'.")


def load_text(path: Path) -> str:
    """Load the text content from *path*, trying UTF-8 first."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Fallback to the system default encoding if UTF-8 fails.
        return path.read_text()


def split_sentences(text: str) -> list[str]:
    """Split *text* into simple sentence-like chunks."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = re.split(r"(?<=[.!?])\s+|\n+", normalized)
    sentences = [part.strip() for part in parts if part.strip()]
    return sentences


def find_keyword_sentences(sentences: list[str], keyword: str) -> list[str]:
    """Return sentences that contain *keyword* (case insensitive)."""
    keyword_lower = keyword.lower()
    matches = [s for s in sentences if keyword_lower in s.lower()]
    return matches


def split_blocks(text: str) -> list[str]:
    """Split raw text into blocks separated by blank lines."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    blocks = re.split(r"\n\s*\n+", normalized)
    return [b.strip() for b in blocks if b.strip()]


def parse_entry_fields(block: str) -> tuple[str | None, str | None, str | None]:
    """Attempt to extract (company, role, location) from a block.

    Tries labeled lines first, then common inline patterns.
    Returns None for fields that aren't found.
    """
    company = role = location = None

    # Labeled lines
    m = re.search(r"(?im)^\s*(Company|Employer|Organization)\s*:\s*(.+?)\s*$", block)
    if m:
        company = m.group(2).strip()
    m = re.search(r"(?im)^\s*(Role|Position|Title)\s*:\s*(.+?)\s*$", block)
    if m:
        role = m.group(2).strip()
    m = re.search(r"(?im)^\s*(Location|City|Remote)\s*:\s*(.+?)\s*$", block)
    if m:
        location = m.group(2).strip()

    # Inline forms if still missing
    if not (company and role and location):
        # Pattern: Company - Role - Location
        m = re.search(r"(?im)^\s*([^\-|\u2013\u2014\|]+?)\s*[\-|\u2013\u2014]\s*([^\-|\u2013\u2014\|]+?)\s*[\-|\u2013\u2014]\s*(.+?)\s*$", block)
        if m:
            company = company or m.group(1).strip()
            role = role or m.group(2).strip()
            location = location or m.group(3).strip()

    if not (company and role):
        # Pattern: Role at Company (Location)
        m = re.search(r"(?im)^\s*(.+?)\s+at\s+(.+?)(?:\s*\((.+?)\))?\s*$", block)
        if m:
            role = role or m.group(1).strip()
            company = company or m.group(2).strip()
            if m.lastindex and m.lastindex >= 3 and m.group(3):
                location = location or m.group(3).strip()

    return company or None, role or None, location or None


def _strip_markdown_inline(text: str) -> str:
    """Remove common inline Markdown/HTML artifacts from a single-line field."""
    t = text
    # images -> alt text
    t = re.sub(r"!\[([^\]]*)\]\((?:[^)]+)\)", r"\1", t)
    # links -> label
    t = re.sub(r"\[([^\]]+)\]\((?:[^)]+)\)", r"\1", t)
    # inline code
    t = re.sub(r"`([^`]*)`", r"\1", t)
    # HTML tags
    t = re.sub(r"<[^>]+>", "", t)
    # collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _entries_to_table(entries: list[tuple[str | None, str | None, str | None, list[str]]], keywords: list[str]) -> list[str]:
    """Convert parsed entries to a clean table (TSV) filtered by keywords.

    Keeps only rows where any sentence in the entry contains at least one
    keyword (case-insensitive).
    """
    def matches_keywords(sents: list[str]) -> bool:
        kl = [k.lower() for k in keywords]
        for s in sents:
            sl = s.lower()
            for k in kl:
                if k and k in sl:
                    return True
        return False

    # Sort and filter
    def sort_key(e: tuple[str | None, str | None, str | None, list[str]]):
        c, r, l, _ = e
        return (c or "", r or "", l or "")

    filtered = [e for e in entries if matches_keywords(e[3])]
    rows = []
    seen = set()
    for company, role, location, _ in sorted(filtered, key=sort_key):
        c = _strip_markdown_inline(company or "") or "-"
        r = _strip_markdown_inline(role or "") or "-"
        l = _strip_markdown_inline(location or "") or "-"
        key = (c, r, l)
        if key in seen:
            continue
        seen.add(key)
        rows.append(f"{c}\t{r}\t{l}")

    lines: list[str] = []
    lines.append("Company\tRole\tLocation")
    if rows:
        lines.extend(rows)
    else:
        lines.append("-")
    return lines


def _extract_td_cells(html_text: str) -> list[tuple[str, str | None]]:
    """Return a flat list of (<td> inner text plain, first href) for each cell."""
    cells: list[tuple[str, str | None]] = []
    for m in re.finditer(r"(?is)<td\b[^>]*>(.*?)</td>", html_text):
        inner = m.group(1)
        # find first href
        href_match = re.search(r"(?is)<a\b[^>]*href\s*=\s*(['\"])\s*([^'\"]+?)\s*\1", inner)
        href = href_match.group(2).strip() if href_match else None
        # strip tags and decode entities
        plain = re.sub(r"(?is)<[^>]+>", "", inner)
        plain = html.unescape(plain)
        plain = re.sub(r"\s+", " ", plain).strip()
        cells.append((plain, href))
    return cells


def _extract_rows_from_html(full_text: str, keywords: list[str]) -> list[tuple[str, str, str, str]]:
    """Return a list of (Company, Role, Location, Link) rows filtered by keywords."""
    cells = _extract_td_cells(full_text)
    kl = [k.lower() for k in keywords if k]
    seen: set[tuple[str, str, str, str]] = set()
    rows: list[tuple[str, str, str, str]] = []

    for i, (text_plain, _) in enumerate(cells):
        lower = text_plain.lower()
        if not any(k in lower for k in kl):
            continue
        # Ensure neighbors exist
        if i - 2 < 0 or i + 1 >= len(cells):
            continue
        company = _strip_markdown_inline(cells[i - 2][0]) or "-"
        role = _strip_markdown_inline(cells[i - 1][0]) or "-"
        location = _strip_markdown_inline(text_plain) or "-"
        link_raw = cells[i + 1][1] or cells[i + 1][0]
        link = (link_raw or "-").strip()
        key = (company, role, location, link)
        if key in seen:
            continue
        seen.add(key)
        rows.append(key)
    return rows


def _format_tsv(rows: list[tuple[str, str, str, str]]) -> str:
    lines = ["Company\tRole\tLocation\tLink"]
    for c, r, l, u in rows:
        lines.append(f"{c}\t{r}\t{l}\t{u}")
    if len(lines) == 1:
        lines.append("-")
    return "\n".join(lines).rstrip() + "\n"


def _format_csv(rows: list[tuple[str, str, str, str]]) -> str:
    def q(s: str) -> str:
        if any(ch in s for ch in [',', '"', '\n', '\r']):
            return '"' + s.replace('"', '""') + '"'
        return s
    lines = ["Company,Role,Location,Link"]
    for c, r, l, u in rows:
        lines.append(
            ",".join([q(c), q(r), q(l), q(u)])
        )
    if len(lines) == 1:
        lines.append("-")
    return "\n".join(lines).rstrip() + "\n"


def format_results(file_path: Path, keywords: list[str], sentences: list[str], full_text: str) -> str:
    """Create TSV output; CSV is generated separately in main."""
    rows = _extract_rows_from_html(full_text, keywords)
    return _format_tsv(rows)


def _format_pretty_table(rows: list[tuple[str, str, str, str]]) -> str:
    """Return a visually aligned plain-text table for easy reading.

    Uses fixed-width columns for Company/Role/Location with soft caps and
    ellipsis for very long values. Link is left as-is following two spaces.
    """
    header = ("Company", "Role", "Location", "Link")
    data = [header] + rows

    # Compute widths with caps to avoid extreme stretching
    def width(col: int, cap: int) -> int:
        return min(max(len(str(r[col])) for r in data), cap)

    w_company = max(8, width(0, 36))
    w_role = max(8, width(1, 48))
    w_location = max(8, width(2, 28))

    def crop(s: str, w: int) -> str:
        s = s.replace("\n", " ").replace("\r", " ")
        return (s[: w - 1] + "…") if len(s) > w else s

    def fmt_row(c: str, r: str, l: str, u: str) -> str:
        c2 = crop(c, w_company).ljust(w_company)
        r2 = crop(r, w_role).ljust(w_role)
        l2 = crop(l, w_location).ljust(w_location)
        return f"{c2}  {r2}  {l2}  {u}"

    lines: list[str] = []
    lines.append(fmt_row(*header))
    lines.append("-" * (w_company + w_role + w_location + 6 + 10))
    for c, r, l, u in rows:
        lines.append(fmt_row(c, r, l, u))
        lines.append("")  # extra space between jobs
    if len(rows) == 0:
        lines.append("-")
    return "\n".join(lines).rstrip() + "\n"


def _format_markdown_table(rows: list[tuple[str, str, str, str]]) -> str:
    """Return a Markdown table with clickable links in the last column."""
    def esc(cell: str) -> str:
        # Minimal escaping for pipes
        return cell.replace("|", "\\|").replace("\n", " ")

    lines: list[str] = []
    lines.append("| Company | Role | Location | Link |")
    lines.append("|---|---|---|---|")
    if not rows:
        lines.append("| - | - | - | - |")
    else:
        for c, r, l, u in rows:
            link_cell = f"[Open]({u})" if u and u != "-" else "-"
            lines.append(f"| {esc(c)} | {esc(r)} | {esc(l)} | {link_cell} |")
    return "\n".join(lines).rstrip() + "\n"


def _dedupe_rows(rows: list[tuple[str, str, str, str]]) -> list[tuple[str, str, str, str]]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[tuple[str, str, str, str]] = []
    for row in rows:
        if row in seen:
            continue
        seen.add(row)
        out.append(row)
    return out


def _is_url_alive(url: str, timeout: float = 4.0) -> bool:
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return False
    headers = {"User-Agent": "txtExtractor/1.0"}
    try:
        req = request.Request(url, method="HEAD", headers=headers)
        with request.urlopen(req, timeout=timeout) as resp:
            code = getattr(resp, "status", 0) or getattr(resp, "code", 0)
            if 200 <= code < 400:
                return True
    except error.HTTPError as e:
        if e.code == 405:
            pass
        elif 200 <= e.code < 400:
            return True
        else:
            return False
    except Exception:
        pass

    try:
        headers2 = dict(headers)
        headers2["Range"] = "bytes=0-0"
        req = request.Request(url, method="GET", headers=headers2)
        with request.urlopen(req, timeout=timeout) as resp:
            code = getattr(resp, "status", 0) or getattr(resp, "code", 0)
            if 200 <= code < 400:
                return True
    except error.HTTPError as e:
        if e.code in (200, 206, 301, 302, 303, 307, 308, 416):
            return True
        return False
    except Exception:
        return False


def _filter_rows_by_live_links(rows: list[tuple[str, str, str, str]], timeout: float = 4.0, max_workers: int = 10) -> list[tuple[str, str, str, str]]:
    if not rows:
        return rows
    idx_to_keep: set[int] = set()
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_is_url_alive, url, timeout): i for i, (_, _, _, url) in enumerate(rows)}
        for fut in as_completed(futures):
            i = futures[fut]
            ok = False
            try:
                ok = fut.result()
            except Exception:
                ok = False
            if ok:
                idx_to_keep.add(i)
    return [row for i, row in enumerate(rows) if i in idx_to_keep]


def main() -> None:
    print("Welcome to txtExtractor!")
    file_path = prompt_file_path()
    keywords = prompt_keywords()

    try:
        text = load_text(file_path)
    except OSError as exc:
        print(f"Failed to read {file_path}: {exc}")
        return

    sentences = split_sentences(text)
    if not sentences:
        print("No text content found in the file.")
        return

    # Build row data from provided file
    rows = _extract_rows_from_html(text, keywords)

    # This tool only parses the provided .md/.txt file. For Eluta.ca scraping,
    # use the separate script: eluta_cli.py

    # Optionally filter out dead links (HTTP check). This may take a few seconds.
    if rows and prompt_yes_no("Filter out jobs with dead links?", default=False):
        try:
            before = len(rows)
            rows = _filter_rows_by_live_links(rows)
            removed = before - len(rows)
            print(f"Filtered {removed} dead-link job(s).")
        except Exception as exc:
            print(f"Link filtering skipped due to error: {exc}")

    # Render outputs in multiple formats
    tsv_text = _format_tsv(rows)
    csv_text = _format_csv(rows)
    pretty_text = _format_pretty_table(rows)
    md_text = _format_markdown_table(rows)

    # Print a quick preview header + first few rows for neatness
    preview_lines = pretty_text.splitlines()
    preview = "\n".join(preview_lines[: min(6, len(preview_lines))])
    print("\n" + preview)

    # Write files next to the source file
    base = file_path.with_name(file_path.stem + "_extracted")
    paths = {
        "txt": base.with_suffix(".txt"),  # TSV in .txt for convenience
        "tsv": base.with_suffix(".tsv"),
        "csv": base.with_suffix(".csv"),
        "md": base.with_suffix(".md"),
    }
    try:
        # .txt gets the pretty-aligned layout; .tsv is strict tab-separated
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
