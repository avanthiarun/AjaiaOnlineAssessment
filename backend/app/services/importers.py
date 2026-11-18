"""Convert uploaded files (.txt, .md, .docx, .odt, .rtf, .html, .pdf) into sanitized document HTML."""

import html
import io
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import PurePosixPath

import mammoth
import markdown
from pypdf import PdfReader
from striprtf.striprtf import rtf_to_text

from app.models.document import TITLE_MAX_LENGTH
from app.services.documents import sanitize_html

SUPPORTED_EXTENSIONS = (".txt", ".md", ".docx", ".odt", ".rtf", ".html", ".htm", ".pdf")
SUPPORTED_LABEL = ", ".join(SUPPORTED_EXTENSIONS[:-1]) + " and " + SUPPORTED_EXTENSIONS[-1]
UNSUPPORTED_MESSAGE = f"Supported files are {SUPPORTED_LABEL}"
LEGACY_DOC_MESSAGE = (
    "Legacy .doc files aren't supported. Open it in Word or Google Docs and save as .docx, "
    "then upload again."
)
ZIP_SIGNATURE = b"PK\x03\x04"
PDF_SIGNATURE = b"%PDF-"
PDF_MAX_PAGES = 50

ODF_NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
}


class UnsupportedFileType(ValueError):
    """The file's extension or content is not one we import."""


def split_filename(filename: str) -> tuple[str, str]:
    """Return (title, lowercase extension); handles Windows-style paths some browsers send."""
    path = PurePosixPath(filename.replace("\\", "/"))
    return path.stem.strip()[:TITLE_MAX_LENGTH], path.suffix.lower()


def check_extension(filename: str) -> None:
    """Raise UnsupportedFileType (with a helpful message) unless we import this extension."""
    ext = split_filename(filename)[1]
    if ext == ".doc":
        raise UnsupportedFileType(LEGACY_DOC_MESSAGE)
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileType(UNSUPPORTED_MESSAGE)


def _decode_text(data: bytes) -> str:
    """Decode UTF-8 (with or without BOM), falling back to latin-1."""
    if b"\x00" in data:
        raise UnsupportedFileType("This does not look like a text file")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _txt_to_html(text: str) -> str:
    """Blank-line-separated blocks become <p>; single newlines become <br>."""
    blocks = [b for b in text.replace("\r\n", "\n").split("\n\n") if b.strip()]
    return "".join(f"<p>{html.escape(b.strip()).replace(chr(10), '<br>')}</p>" for b in blocks)


def _docx_to_html(data: bytes) -> str:
    """Convert .docx with mammoth (keeping underline, which mammoth drops by default)."""
    if not data.startswith(ZIP_SIGNATURE):
        raise UnsupportedFileType("This does not look like a .docx file")
    try:
        return mammoth.convert_to_html(io.BytesIO(data), style_map="u => u").value
    except Exception as exc:  # mammoth/zipfile raise many different error types
        raise ValueError("Could not read this .docx file") from exc


def _html_to_html(data: bytes) -> tuple[str | None, str]:
    """Return (<title> text or None, markup without <head>); sanitizing happens later."""
    text = _decode_text(data)
    match = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    title = html.unescape(match.group(1)).strip()[:TITLE_MAX_LENGTH] if match else None
    body = re.sub(r"<head\b.*?</head>", "", text, flags=re.IGNORECASE | re.DOTALL)
    return title or None, body


def _rtf_to_html(data: bytes) -> str:
    """Extract plain text from .rtf. Formatting (bold, headings, lists) is not preserved."""
    text = _decode_text(data)
    if not text.lstrip().startswith("{\\rtf"):
        raise UnsupportedFileType("This does not look like an .rtf file")
    try:
        return _txt_to_html(rtf_to_text(text))
    except Exception as exc:  # striprtf raises plain Exceptions on malformed input
        raise ValueError("Could not read this .rtf file") from exc


def _pdf_to_html(data: bytes) -> str:
    """Extract selectable text from the first PDF_MAX_PAGES pages as plain paragraphs."""
    if not data.startswith(PDF_SIGNATURE):
        raise UnsupportedFileType("This does not look like a .pdf file")
    try:
        reader = PdfReader(io.BytesIO(data))
        encrypted = reader.is_encrypted
        pages = [] if encrypted else [p.extract_text() or "" for p in reader.pages[:PDF_MAX_PAGES]]
    except Exception as exc:  # malformed PDFs raise many different error types
        raise ValueError("Could not read this .pdf file") from exc
    if encrypted:
        raise ValueError("Password-protected PDFs aren't supported")
    text = "\n\n".join(pages)
    if not text.strip():
        raise ValueError("This PDF has no selectable text (scanned PDFs aren't supported)")
    return _txt_to_html(text)


def _odf(tag: str) -> str:
    """Expand 'prefix:name' to ElementTree's '{namespace}name' form."""
    prefix, name = tag.split(":")
    return f"{{{ODF_NS[prefix]}}}{name}"


def _odt_marks(root: ET.Element) -> dict[str, list[str]]:
    """Map automatic style names to the inline tags they imply (strong/em/u)."""
    marks: dict[str, list[str]] = {}
    for style in root.iter(_odf("style:style")):
        props = style.find("style:text-properties", ODF_NS)
        if props is None:
            continue
        tags = []
        if props.get(_odf("fo:font-weight")) == "bold":
            tags.append("strong")
        if props.get(_odf("fo:font-style")) == "italic":
            tags.append("em")
        if props.get(_odf("style:text-underline-style"), "none") != "none":
            tags.append("u")
        marks[style.get(_odf("style:name"), "")] = tags
    return marks


def _odt_inline(el: ET.Element, marks: dict[str, list[str]]) -> str:
    """Render the inline content of a paragraph/heading/span."""
    out = [html.escape(el.text or "")]
    for child in el:
        if child.tag == _odf("text:s"):
            out.append(" " * int(child.get(_odf("text:c"), "1")))
        elif child.tag == _odf("text:tab"):
            out.append(" ")
        elif child.tag == _odf("text:line-break"):
            out.append("<br>")
        else:
            out.append(_odt_wrap(_odt_inline(child, marks), child, marks))
        out.append(html.escape(child.tail or ""))
    return "".join(out)


def _odt_wrap(inner: str, el: ET.Element, marks: dict[str, list[str]]) -> str:
    """Wrap content in the strong/em/u tags of the element's style, if any."""
    for tag in marks.get(el.get(_odf("text:style-name"), ""), []):
        inner = f"<{tag}>{inner}</{tag}>"
    return inner


def _odt_blocks(parent: ET.Element, marks: dict[str, list[str]]) -> str:
    """Render block children: headings (capped at h3), paragraphs and bulleted lists."""
    out = []
    for el in parent:
        if el.tag == _odf("text:h"):
            level = min(max(int(el.get(_odf("text:outline-level"), "1")), 1), 3)
            out.append(f"<h{level}>{_odt_wrap(_odt_inline(el, marks), el, marks)}</h{level}>")
        elif el.tag == _odf("text:p"):
            out.append(f"<p>{_odt_wrap(_odt_inline(el, marks), el, marks)}</p>")
        elif el.tag == _odf("text:list"):
            items = el.findall("text:list-item", ODF_NS)
            out.append("<ul>" + "".join(f"<li>{_odt_blocks(i, marks)}</li>" for i in items) + "</ul>")
        else:  # sections, tables, etc.: keep their text content
            out.append(_odt_blocks(el, marks))
    return "".join(out)


def _odt_to_html(data: bytes) -> str:
    """Convert .odt by reading content.xml directly.

    We parse content.xml rather than using odfpy's ODF2XHTML because, with generate_css=False,
    ODF2XHTML drops bold/italic and (in embedable mode) emits no <body> element.
    """
    if not data.startswith(ZIP_SIGNATURE):
        raise UnsupportedFileType("This does not look like an .odt file")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if "content.xml" not in archive.namelist():
                raise UnsupportedFileType("This does not look like an .odt file")
            root = ET.fromstring(archive.read("content.xml"))
    except (zipfile.BadZipFile, ET.ParseError) as exc:
        raise ValueError("Could not read this .odt file") from exc
    body = root.find("office:body/office:text", ODF_NS)
    if body is None:
        raise UnsupportedFileType("This does not look like an .odt text document")
    return _odt_blocks(body, _odt_marks(root))


def file_to_html(filename: str, data: bytes) -> tuple[str, str]:
    """Return (title, sanitized html) for an uploaded file.

    Raises UnsupportedFileType for unknown types and ValueError for unparseable files.
    """
    check_extension(filename)
    title, ext = split_filename(filename)
    if ext == ".txt":
        body = _txt_to_html(_decode_text(data))
    elif ext == ".md":
        body = markdown.markdown(_decode_text(data), extensions=["extra", "sane_lists"])
    elif ext == ".docx":
        body = _docx_to_html(data)
    elif ext == ".odt":
        body = _odt_to_html(data)
    elif ext == ".rtf":
        body = _rtf_to_html(data)
    elif ext == ".pdf":
        body = _pdf_to_html(data)
    else:  # .html / .htm
        html_title, body = _html_to_html(data)
        title = html_title or title
    return title, sanitize_html(body)
