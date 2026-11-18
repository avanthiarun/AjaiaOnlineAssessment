"""Regenerate sample.pdf: `python tests/fixtures/make_sample_pdf.py` from backend/.

Writes a minimal one-page PDF by hand (no extra dependency) with two lines of real,
selectable Helvetica text separated by a gap, so pypdf can extract them.
"""

from pathlib import Path

CONTENT = (
    b"BT /F1 18 Tf 72 720 Td (Quarterly report) Tj ET\n"
    b"BT /F1 12 Tf 72 660 Td (Revenue grew in every region.) Tj ET\n"
)
OBJECTS = [
    b"<< /Type /Catalog /Pages 2 0 R >>",
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
    b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    b"<< /Length %d >>\nstream\n" % len(CONTENT) + CONTENT + b"endstream",
]


def build() -> bytes:
    """Assemble the objects with a correct cross-reference table."""
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(OBJECTS, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(OBJECTS) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(OBJECTS) + 1, xref)
    return bytes(out)


if __name__ == "__main__":
    Path(__file__).with_name("sample.pdf").write_bytes(build())
