import re
from pathlib import Path

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

    print("\nResults:\n--------")
    for keyword in keywords:
        matches = find_keyword_sentences(sentences, keyword)
        if matches:
            print(f"\nKeyword: '{keyword}'")
            for sentence in matches:
                print(f"- {sentence}")
        else:
            print(f"\nKeyword: '{keyword}' -> No matches found.")


if __name__ == "__main__":
    main()
