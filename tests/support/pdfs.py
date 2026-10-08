"""Small real PDFs, made in the test (nothing binary is committed), so the Reader is tested through the real pypdf.

`make_pdf(["page one text", "", "page three"])`: one page per item, an empty string is a page with no text (what a scan looks like to a text extractor).
Text is Latin-1; a newline starts a new line on the page.
"""

from __future__ import annotations

import io
import zlib

from pypdf import PdfReader, PdfWriter


def _escape(line: str) -> str:
    return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _stream(text: str) -> bytes:
    if not text:
        return b""
    lines = text.split("\n")
    body = "BT /F1 12 Tf 72 720 Td 14 TL " + " T* ".join(f"({_escape(line)}) Tj" for line in lines) + " ET"
    return body.encode("latin-1")


def make_pdf(pages: list[str], *, flate_pages: set[int] = frozenset()) -> bytes:
    """`flate_pages`: indexes of pages whose content stream is stored compressed (needed to build a huge page in a few KB)."""
    n = len(pages)
    bodies: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(f'{4 + 2 * i} 0 R' for i in range(n))}] /Count {n} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, text in enumerate(pages):
        bodies.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {5 + 2 * i} 0 R /Resources << /Font << /F1 3 0 R >> >> >>".encode()
        )
        stream = _stream(text)
        if i in flate_pages:
            stream = zlib.compress(stream)
            bodies.append(f"<< /Length {len(stream)} /Filter /FlateDecode >>\nstream\n".encode() + stream + b"\nendstream")
        else:
            bodies.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(bodies, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(bodies) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(bodies) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def encrypted(pdf: bytes, password: str) -> bytes:
    """The same PDF, locked with a password the Reader does not have (RC4, which needs no extra library)."""
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(pdf)))
    writer.encrypt(password, algorithm="RC4-128")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
