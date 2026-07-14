from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from monitor.fingerprint import normalize_text
from monitor.schema import Source


USER_AGENT = "GeologyJobRadar/1.0 (+https://github.com/healerLSC/geology-job-radar)"
TIMEOUT = (10, 30)


@dataclass(frozen=True)
class FetchResult:
    source_id: str
    status: str
    url: str
    text: str
    links: tuple[str, ...]
    content_type: str
    error: str | None = None


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"})
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup.select("script, style, noscript, nav, footer, svg"):
        element.decompose()
    return normalize_text(soup.get_text(" ", strip=True))


def html_links(html: str, base_url: str) -> tuple[str, ...]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        clean = parsed._replace(fragment="").geturl()
        if clean not in seen:
            seen.add(clean)
            links.append(clean)
    return tuple(links)


def extract_document_text(content: bytes, content_type: str, url: str) -> str:
    suffix = PurePosixPath(urlparse(url).path).suffix.lower()
    lowered_type = content_type.lower()
    if suffix == ".pdf" or "application/pdf" in lowered_type:
        reader = PdfReader(BytesIO(content))
        return normalize_text(" ".join(page.extract_text() or "" for page in reader.pages))
    if suffix == ".docx" or "wordprocessingml.document" in lowered_type:
        document = Document(BytesIO(content))
        chunks = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            chunks.extend(cell.text for row in table.rows for cell in row.cells)
        return normalize_text(" ".join(chunks))
    if suffix == ".xlsx" or "spreadsheetml.sheet" in lowered_type:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        chunks: list[str] = []
        for worksheet in workbook.worksheets:
            for row in worksheet.iter_rows(values_only=True):
                chunks.append(" ".join(str(value) for value in row if value is not None))
        workbook.close()
        return normalize_text(" ".join(chunks))
    if lowered_type.startswith("text/"):
        return normalize_text(content.decode("utf-8", errors="replace"))
    return ""


def fetch_source(source: Source, session: requests.Session | None) -> FetchResult:
    if source.mode == "restricted":
        return FetchResult(source.source_id, "restricted", source.url, "", (), "", "公开抓取受限")
    if session is None:
        return FetchResult(source.source_id, "failed", source.url, "", (), "", "缺少网络会话")
    try:
        response = session.get(source.url, timeout=TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if "html" in content_type or not content_type:
            html = response.text
            text = html_to_text(html)
            links = html_links(html, response.url)
        else:
            text = extract_document_text(response.content, content_type, response.url)
            links = ()
        return FetchResult(
            source.source_id,
            "success" if text else "failed",
            response.url,
            text,
            links,
            content_type,
            None if text else "未提取到可用正文",
        )
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        status = "restricted" if status_code in {401, 403, 429} else "failed"
        return FetchResult(source.source_id, status, source.url, "", (), "", str(exc))
    except (requests.RequestException, OSError, ValueError) as exc:
        return FetchResult(source.source_id, "failed", source.url, "", (), "", str(exc))
