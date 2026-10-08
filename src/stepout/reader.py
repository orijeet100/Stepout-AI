"""Reader: how the Assistant reads the contents of a file. Text files and PDFs only, read-only, and only where the User granted `read`.

Every path goes through `Files.resolve_readable` (shape, real path, block list, a grant in `read` mode): the same refusals as the
`files` tool. Then, per Run: at most 20 files and 10 MB. Per file: the type is decided by its content (a name proves nothing), its
text is screened for secrets (redact.py) and cut to 40,000 characters, and the whole read runs in a worker thread with a time limit,
so a hostile file can spoil one read but never freeze the Assistant. No OCR: a scanned PDF is reported as having no text.

What comes back is data from a file, written by anyone: untrusted, never instructions.
"""

from __future__ import annotations

import asyncio
import codecs
import io
import os
import re
from dataclasses import dataclass

from pypdf import PdfReader

from stepout.files import Files, _clean, _size
from stepout.redact import redact

MAX_FILES = 20  # per Run
MAX_BYTES = 10 * 1024 * 1024  # per Run, counted over the files opened
MAX_CHARS = 40_000  # of one file's text sent on
_WINDOW = MAX_CHARS + 1_000  # screened together, so a secret across the cut is caught
MAX_PDF_PAGES = 200
MAX_PAGE_STREAM = 5 * 1024 * 1024  # decompressed bytes of one page's content: pypdf's docs warn that extraction needs memory for all of it
READ_SECONDS = 30

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f​-‏‪-‮⁠-⁤⁦-⁩﻿]")  # controls, zero-width and bidi tricks


@dataclass
class ReadUsage:
    """What one Run has read so far."""

    files: int = 0
    bytes: int = 0


@dataclass
class ReadResult:
    text: str  # what goes into the Role's notes
    content: bool  # file text is in it (so the Run now holds data that came from the User's files)


def _decode(data: bytes) -> str | None:
    """Text from bytes, or None if they are not text."""
    if data.startswith(codecs.BOM_UTF8):
        text = data[3:].decode("utf-8", "replace")
    elif data[:2] in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE):
        text = data.decode("utf-16", "replace")
    elif b"\x00" in data[:8192]:
        return None
    else:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("cp1252", "replace")
    sample = text[:8192]
    odd = sum(1 for c in sample if (ord(c) < 32 and c not in "\n\r\t") or c == "�")
    return None if sample and odd > len(sample) * 0.1 else text


def _pdf(data: bytes) -> tuple[str, str, bool]:
    """-> (text, note, stopped_early): the text of the first pages, up to the window; the note says what was left out or why there is no text.
    `stopped_early`: extraction stopped before the last page, so the true length of the text is not known."""
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted and not reader.decrypt(""):
            return "", "it is encrypted and needs a password, so it was not opened", False
        total = len(reader.pages)
        parts, chars, done, skipped = [], 0, 0, 0
        for i in range(min(total, MAX_PDF_PAGES)):
            done = i + 1  # visited, even if its text turns out unusable
            try:
                page = reader.pages[i]
                contents = page.get_contents()
                if contents is not None and len(contents.get_data()) > MAX_PAGE_STREAM:
                    skipped += 1  # the docs' own advice: look before extracting a huge page
                    continue
                text = page.extract_text() or ""
            except Exception:  # one bad page does not lose the others
                text = ""
            parts.append(text)
            chars += len(text)
            if chars >= _WINDOW:
                break
        note = f"pages 1-{done} of {total}" if done < total else f"{total} page{'s' if total != 1 else ''}"
        if total > MAX_PDF_PAGES and done >= MAX_PDF_PAGES:
            note += f" (at most {MAX_PDF_PAGES} are read)"
        if skipped:
            note += f"; {skipped} too large to read safely"
        return "\n\n".join(parts), note, done < min(total, MAX_PDF_PAGES) or total > MAX_PDF_PAGES
    except Exception as exc:  # malformed, truncated or hostile: whatever pypdf says, it is not a readable PDF
        return "", f"it could not be read as a PDF ({type(exc).__name__})", False


class Reader:
    def __init__(self, files: Files) -> None:
        self._files = files

    async def read(self, path: str, usage: ReadUsage) -> ReadResult:
        try:
            return await asyncio.wait_for(asyncio.to_thread(self._read, path, usage), READ_SECONDS)
        except asyncio.TimeoutError:
            # ponytail: the thread cannot be killed, so a pathological file can keep one worker busy after this; the fix is a subprocess
            return ReadResult(f"Error: reading took longer than {READ_SECONDS} seconds and was stopped. Nothing from this file was read.", False)

    def _read(self, path: str, usage: ReadUsage) -> ReadResult:
        real, why = self._files.resolve_readable(path)
        if real is None:
            return ReadResult(f"Denied: {why}", False)
        if usage.files >= MAX_FILES:
            return ReadResult(f"Limit: this task has already read {MAX_FILES} files, the most allowed. Answer with what you have.", False)
        left = MAX_BYTES - usage.bytes
        try:
            if os.path.getsize(real) > left:
                return ReadResult(f"Limit: this file is {_size(os.path.getsize(real))} and only {_size(left)} of the task's 10 MB read budget is left. It was not opened.", False)
            with open(real, "rb") as f:
                if os.path.normcase(os.path.realpath(real)) != os.path.normcase(real):  # swapped for a link between the check and the open
                    return ReadResult("Denied: the file changed while it was being opened.", False)
                data = f.read(left + 1)
        except OSError as exc:
            return ReadResult(f"Error: could not read the file ({exc.strerror or type(exc).__name__}).", False)
        if len(data) > left:
            return ReadResult(f"Limit: this file is larger than the {_size(left)} of the task's 10 MB read budget that is left. It was not read.", False)
        usage.files += 1
        usage.bytes += len(data)

        name = _clean(real, 250)
        stopped_early = False
        if data.startswith(b"%PDF-"):
            text, note, stopped_early = _pdf(data)
            kind = f"PDF, {_size(len(data))}, {note}"
            if not text.strip():
                return ReadResult(f"read_text {name}: {kind}. No text could be extracted from it: it may be scanned images, and the Assistant does not do OCR. Do not guess its contents.", False)
        else:
            text = _decode(data)
            if text is None:
                return ReadResult(f"read_text {name}: this is not a text file or a PDF, so it was not read.", False)
            kind = f"text, {_size(len(data))}"
            if not text.strip():
                return ReadResult(f"read_text {name}: {kind}. The file is empty.", False)

        text = _CONTROL.sub("", text.replace("\r\n", "\n"))
        total = len(text)
        screened, secrets = redact(text[:_WINDOW])
        shown = screened[:MAX_CHARS]
        if stopped_early:  # the real length is unknown: only say what is shown
            notes = [f"the first {MAX_CHARS:,} characters are shown; the rest was not read"]
        elif total > MAX_CHARS:
            notes = [f"the first {MAX_CHARS:,} of {total:,} characters are shown; the rest was not sent"]
        else:
            notes = [f"{total:,} characters"]
        if secrets:
            notes.append(f"{secrets} secret-looking value{'s' if secrets != 1 else ''} replaced with [redacted]")
        return ReadResult(f"read_text {name}: {kind}; " + "; ".join(notes) + f"\n{shown}", True)
