import re
import time
import ssl
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple
from urllib import error, parse, request


DEFAULT_USER_AGENT = (
    # Some environments/proxies block non-browser UAs; use a common one.
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


@dataclass
class Job:
    company: str
    role: str
    location: str
    link: str


def _http_get(url: str, timeout: float = 8.0, user_agent: str = DEFAULT_USER_AGENT) -> str:
    headers = {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"}
    req = request.Request(url, headers=headers)

    def _read_with_context(ctx: Optional[ssl.SSLContext]):
        if ctx is None:
            resp = request.urlopen(req, timeout=timeout)
        else:
            resp = request.urlopen(req, timeout=timeout, context=ctx)
        with resp:
            data = resp.read()
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return data.decode("iso-8859-1", errors="replace")

    # Try with a default secure context first
    ctx1 = ssl.create_default_context()
    try:
        return _read_with_context(ctx1)
    except Exception as e:
        # Fallback: relax OpenSSL security level to improve proxy compatibility
        try:
            ctx2 = ssl.create_default_context()
            # Prefer TLS1.2+; some proxies fail unless seclevel is lowered
            if hasattr(ssl, "TLSVersion"):
                try:
                    ctx2.minimum_version = ssl.TLSVersion.TLSv1_2  # type: ignore[attr-defined]
                except Exception:
                    pass
            try:
                ctx2.set_ciphers("DEFAULT:@SECLEVEL=1")
            except Exception:
                # set_ciphers may not be available or allowed; ignore
                pass
            return _read_with_context(ctx2)
        except Exception:
            raise


def build_search_url(query: str, location: Optional[str] = None, page: int = 1) -> str:
    # Eluta commonly supports /search?q=...&l=...&p=...
    # This may evolve; keep it configurable via inputs.
    q = (query or "").strip()
    l = (location or "").strip()
    params = {"q": q}
    if l:
        params["l"] = l
    if page and page > 1:
        params["p"] = str(page)
    return "https://www.eluta.ca/search?" + parse.urlencode(params)


def _clean_text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"&amp;", "&", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _find_result_blocks(html_text: str) -> List[str]:
    # Try common containers: <article ...> ... </article> or <div class="result ..."> ... </div>
    blocks: List[str] = []
    # article blocks
    for m in re.finditer(r"(?is)<article\b[^>]*>(.*?)</article>", html_text):
        blocks.append(m.group(1))
    # fallback to divs that look like results
    if not blocks:
        for m in re.finditer(r"(?is)<div\b[^>]*class=\"[^\"]*(?:result|job)[^\"]*\"[^>]*>(.*?)</div>", html_text):
            blocks.append(m.group(1))
    return blocks


def _extract_link_and_title(block_html: str) -> Tuple[str, str]:
    # Prefer anchor with job title-like class; otherwise first anchor
    m = re.search(r"(?is)<a\b[^>]*class\s*=\s*['\"][^'\"]*(?:title|job|posting)[^'\"]*['\"][^>]*href\s*=\s*['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", block_html)
    if not m:
        m = re.search(r"(?is)<a\b[^>]*href\s*=\s*['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", block_html)
    if not m:
        return "", ""
    href = _clean_text(m.group(1))
    title = _clean_text(m.group(2))
    return href, title


def _extract_company(block_html: str) -> str:
    # Look for explicit company containers
    patterns = [
        r"(?is)<div\b[^>]*class\s*=\s*['\"][^'\"]*(?:company|employer)[^'\"]*['\"][^>]*>(.*?)</div>",
        r"(?is)<span\b[^>]*class\s*=\s*['\"][^'\"]*(?:company|employer)[^'\"]*['\"][^>]*>(.*?)</span>",
        r"(?is)<a\b[^>]*class\s*=\s*['\"][^'\"]*(?:company|employer)[^'\"]*['\"][^>]*>(.*?)</a>",
    ]
    for pat in patterns:
        m = re.search(pat, block_html)
        if m:
            return _clean_text(m.group(1))
    # Fallback: second anchor text (often company)
    anchors = list(re.finditer(r"(?is)<a\b[^>]*>(.*?)</a>", block_html))
    if len(anchors) >= 2:
        return _clean_text(anchors[1].group(1))
    return ""


def _extract_location(block_html: str) -> str:
    patterns = [
        r"(?is)<div\b[^>]*class\s*=\s*['\"][^'\"]*(?:location|cities)[^'\"]*['\"][^>]*>(.*?)</div>",
        r"(?is)<span\b[^>]*class\s*=\s*['\"][^'\"]*(?:location|city)[^'\"]*['\"][^>]*>(.*?)</span>",
    ]
    for pat in patterns:
        m = re.search(pat, block_html)
        if m:
            return _clean_text(m.group(1))
    # Fallback: look for city/province-like tokens
    m2 = re.search(r"(?is)\b([A-Z][a-z]+(?:[,\s]+(?:ON|QC|BC|AB|MB|SK|NS|NB|NL|PE|YT|NT|NU)))\b", _clean_text(block_html))
    if m2:
        return _clean_text(m2.group(1))
    return ""


def parse_results(html_text: str) -> List[Job]:
    jobs: List[Job] = []
    for block in _find_result_blocks(html_text):
        href, title = _extract_link_and_title(block)
        if not title:
            continue
        company = _extract_company(block)
        location = _extract_location(block)
        link = href
        jobs.append(Job(company=company or "-", role=title or "-", location=location or "-", link=link or "-"))
    # De-duplicate by (company, role, location, link)
    uniq: List[Job] = []
    seen = set()
    for j in jobs:
        key = (j.company, j.role, j.location, j.link)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(j)
    return uniq


def search_eluta(
    query: str,
    location: Optional[str] = None,
    pages: int = 1,
    delay_sec: float = 0.8,
    *,
    raise_on_error: bool = False,
) -> List[Job]:
    results: List[Job] = []
    for p in range(1, max(1, pages) + 1):
        url = build_search_url(query=query, location=location, page=p)
        try:
            html_text = _http_get(url)
        except error.HTTPError as e:
            if raise_on_error:
                raise
            # Stop on 4xx/5xx
            break
        except Exception:
            if raise_on_error:
                raise
            break
        page_jobs = parse_results(html_text)
        if not page_jobs and p > 1:
            # Likely no more pages
            break
        results.extend(page_jobs)
        if p < pages:
            time.sleep(max(0.0, delay_sec))
    # Final de-dupe across pages
    uniq: List[Job] = []
    seen = set()
    for j in results:
        key = (j.company, j.role, j.location, j.link)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(j)
    return uniq


def jobs_to_rows(jobs: Iterable[Job]) -> List[Tuple[str, str, str, str]]:
    return [(j.company or "-", j.role or "-", j.location or "-", j.link or "-") for j in jobs]
