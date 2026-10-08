"""Hostile PDFs against the Reader hand and the read_text capability: files built to hang, exhaust memory or crash a PDF library.

Every file is made here from the standard library (zlib, a fixed random seed): nothing binary is committed, and none is more than ~1 MB on
disk. Each must be read without raising, in well under the 10 s bound below, with a plain one-line message and `content` False (so it
taints nothing). They guard two layers: pypdf's own cap on one stream's decompression (a bomb just past it) and the Reader's limits
(MAX_PDF_PAGES, MAX_PAGE_STREAM, READ_SECONDS). An upgrade or an edit that loses either layer fails here.
"""

import random
import sys
import time
import zlib

import pytest

from stepout import reader as reader_mod
from stepout.capabilities.base import RunState
from stepout.capabilities.read_text import ReadText, ReadTextAction
from stepout.files import Files, Grant
from stepout.reader import Reader
from tests.support.pdfs import encrypted, make_pdf
from tests.test_reader import ctx_for, norm, read

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows paths")

FAST = 10.0  # seconds; every case here takes well under one on a normal machine, so this is slack for a slow one


@pytest.fixture
def folder(tmp_path):
    g = tmp_path / "granted"
    g.mkdir()
    return g


@pytest.fixture
def reader(folder):
    return Reader(Files([Grant(norm(folder), "read")]))


# --- making the files (make_pdf only builds well-formed text PDFs; these need raw objects) -------------------------------------


def _pdf(objects: list[bytes]) -> bytes:
    """A PDF from raw objects (object 1 is the catalog), with a correct xref table."""
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def _tree(count: bytes, kids: bytes) -> bytes:
    """A page tree whose /Kids and /Count are whatever the test says."""
    return _pdf([
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [" + kids + b"] /Count " + count + b" >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >>",
    ])


def _packed_page(unit: bytes, times: int) -> bytes:
    """One page whose content stream is `unit` repeated `times` times, Flate-compressed a chunk at a time (a few KB on disk).
    It has a font, so text extraction really starts if nothing stops it."""
    packer = zlib.compressobj()
    data = b"".join(packer.compress(unit) for _ in range(times)) + packer.flush()
    return _pdf([
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(data) + data + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ])


def _bomb(megabytes: int) -> bytes:
    """A page that unpacks to `megabytes` MB of spaces (about 1 KB of file per MB). Spaces, so that if a guard is lost the
    page costs seconds, not gigabytes, and the test fails instead of freezing the machine."""
    return _packed_page(b" " * 2**20, megabytes)


# pypdf stops one Flate stream at 75,000,000 bytes (pypdf.Configuration.zlib_maximum_output_length): 80 MB is just past it, and
# 50 MB is under it but over the Reader's own MAX_PAGE_STREAM (5 MB).
CASES = [
    # (how to build the file, words its message must contain)
    # Past pypdf's cap: pypdf itself refuses the stream. If it ever stops doing that, the Reader's "too large" note appears between "1 page" and "No text".
    pytest.param(lambda: _bomb(80), "1 page. No text could be extracted", id="bomb-past-pypdfs-cap"),
    pytest.param(lambda: _bomb(50), "1 page; 1 too large to read safely. No text could be extracted", id="bomb-under-pypdfs-cap-over-ours"),
    pytest.param(lambda: b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R", "could not be read as a PDF", id="truncated"),
    pytest.param(lambda: b"%PDF-1.4\n" + random.Random(7).randbytes(5000), "could not be read as a PDF", id="garbage-behind-a-pdf-header"),
    pytest.param(lambda: random.Random(7).randbytes(5000), "not a text file or a PDF", id="garbage-with-no-header"),
    pytest.param(lambda: _tree(b"2", b"2 0 R 3 0 R"), "could not be read as a PDF", id="page-tree-that-contains-itself"),
    pytest.param(lambda: _tree(b"2000000000", b"3 0 R"), "No text could be extracted", id="page-count-of-two-billion"),
    pytest.param(lambda: encrypted(make_pdf(["secret plans"]), "pw"), "encrypted and needs a password", id="encrypted"),
]


# --- the cases ------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("build, message", CASES)
async def test_a_hostile_pdf_is_read_fast_with_a_plain_message_and_taints_nothing(reader, folder, build, message):
    f = folder / "hostile.pdf"
    f.write_bytes(build())
    assert f.stat().st_size < 200_000
    started = time.perf_counter()
    result = await read(reader, f)  # does not raise
    elapsed = time.perf_counter() - started
    assert elapsed < FAST, f"took {elapsed:.1f} s"
    assert message in result.text, result.text
    assert "\n" not in result.text and "secret plans" not in result.text  # one line, nothing of the file in it
    assert not result.content
    state = RunState()  # the capability is the only thing that taints a Run, and only when file text came back
    await ReadText().run(ReadTextAction(path=str(f)), ctx_for(reader, state))
    assert not state.tainted


async def test_five_thousand_pages_are_read_to_the_page_cap_and_say_so(reader, folder):
    pages = [""] * 5000
    pages[0], pages[1], pages[250], pages[-1] = "first page text", "second page text", "page 251 text", "last page text"
    f = folder / "five-thousand.pdf"
    f.write_bytes(make_pdf(pages))
    started = time.perf_counter()
    result = await read(reader, f)
    elapsed = time.perf_counter() - started
    assert elapsed < FAST, f"took {elapsed:.1f} s"
    head = result.text.splitlines()[0]
    assert "pages 1-200 of 5000 (at most 200 are read)" in head
    assert result.content and "first page text" in result.text and "second page text" in result.text
    assert "page 251 text" not in result.text and "last page text" not in result.text  # past the cap: never read
    state = RunState()
    await ReadText().run(ReadTextAction(path=str(f)), ctx_for(reader, state))
    assert state.tainted  # real text did come back, so this one does taint


async def test_a_page_that_is_only_slow_is_stopped_by_the_time_limit(reader, folder, monkeypatch):
    """Under every other limit (0.5 MB unpacked, 1 page) but slow in pypdf: only READ_SECONDS can stop it. Last, because the worker
    thread cannot be killed (see Reader.read) and the test run waits for it to finish, about a second."""
    assert 0 < reader_mod.READ_SECONDS <= 60  # the real limit, before this test shortens it
    f = folder / "slow.pdf"
    f.write_bytes(_packed_page(b"0 " * 2**18, 1))
    monkeypatch.setattr(reader_mod, "READ_SECONDS", 0.05)
    started = time.perf_counter()
    result = await read(reader, f)
    elapsed = time.perf_counter() - started
    assert not result.content and "took longer than 0.05 seconds" in result.text
    assert elapsed < 1.5, f"took {elapsed:.1f} s"  # stopped at once, not after the whole extraction
