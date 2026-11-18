"""Convert uploaded .txt, .md and .docx files into sanitized document HTML."""

import html
import io
from pathlib import PurePosixPath

import mammoth
import markdown

from app.models.document import TITLE_MAX_LENGTH
from app.services.documents import sanitize_html

SUPPORTED_EXTENSIONS = (".txt", ".md", ".docx")
UNSUPPORTED_MESSAGE = "Supported files are .txt, .md and .docx"
ZIP_SIGNATURE = b"PK\x03\x04"


class UnsupportedFileType(ValueError):
    """The file's extension or content is not one we import."""


def split_filename(filename: str) -> tuple[str, str]:
    """Return (title, lowercase extension); handles Windows-style paths some browsers send."""
    path = PurePosixPath(filename.replace("\\", "/"))
    return path.stem.strip()[:TITLE_MAX_LENGTH], path.suffix.lower()


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


def file_to_html(filename: str, data: bytes) -> tuple[str, str]:
    """Return (title, sanitized html) for an uploaded file.

    Raises UnsupportedFileType for unknown types and ValueError for unparseable files.
    """
    title, ext = split_filename(filename)
    if ext == ".txt":
        body = _txt_to_html(_decode_text(data))
    elif ext == ".md":
        body = markdown.markdown(_decode_text(data), extensions=["extra", "sane_lists"])
    elif ext == ".docx":
        body = _docx_to_html(data)
    else:
        raise UnsupportedFileType(UNSUPPORTED_MESSAGE)
    return title, sanitize_html(body)
