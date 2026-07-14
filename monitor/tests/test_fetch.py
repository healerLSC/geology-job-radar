from io import BytesIO
from pathlib import Path

from docx import Document
from openpyxl import Workbook
import requests

from monitor.fetch import extract_document_text, fetch_source, html_to_text
from monitor.schema import Source


FIXTURE = Path(__file__).parent / "fixtures/recruitment.html"


class FakeResponse:
    status_code = 200
    content = FIXTURE.read_bytes()
    text = content.decode("utf-8")
    headers = {"content-type": "text/html; charset=utf-8"}
    url = "https://example.com/careers/"

    def raise_for_status(self):
        return None


class FakeSession:
    def get(self, url, **kwargs):
        assert kwargs["timeout"] == (10, 30)
        return FakeResponse()


class ForbiddenResponse(FakeResponse):
    status_code = 403

    def raise_for_status(self):
        raise requests.HTTPError("403 Client Error", response=self)


class ForbiddenSession:
    def get(self, url, **kwargs):
        return ForbiddenResponse()


def make_source(mode="html"):
    return Source(
        source_id="example",
        name="示例官方招聘",
        url="https://example.com/careers/",
        source_type="集团官网公告",
        trust="official",
        unit_ids=("example",),
        mode=mode,
        official_domains=("example.com",),
    )


def test_html_to_text_drops_navigation_and_scripts():
    text = html_to_text(FIXTURE.read_text(encoding="utf-8"))
    assert "地质学" in text
    assert "window.__STATE__" not in text
    assert "网站导航" not in text


def test_fetch_source_returns_absolute_candidate_links():
    result = fetch_source(make_source(), FakeSession())
    assert result.status == "success"
    assert "地质学" in result.text
    assert result.links == (
        "https://example.com/notice/2027-geology.html",
        "https://example.com/files/jobs.xlsx",
    )


def test_restricted_source_does_not_attempt_network():
    result = fetch_source(make_source(mode="restricted"), None)
    assert result.status == "restricted"
    assert result.text == ""


def test_access_control_is_reported_as_restricted():
    result = fetch_source(make_source(), ForbiddenSession())
    assert result.status == "restricted"


def test_docx_and_xlsx_text_is_extractable():
    document_buffer = BytesIO()
    document = Document()
    document.add_paragraph("地质学硕士")
    document.save(document_buffer)

    workbook_buffer = BytesIO()
    workbook = Workbook()
    workbook.active.append(["岗位", "专业"])
    workbook.active.append(["矿山地质", "地质学"])
    workbook.save(workbook_buffer)

    assert "地质学硕士" in extract_document_text(
        document_buffer.getvalue(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "https://example.com/jobs.docx",
    )
    assert "矿山地质 地质学" in extract_document_text(
        workbook_buffer.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "https://example.com/jobs.xlsx",
    )
