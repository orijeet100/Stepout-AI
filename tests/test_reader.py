"""The Reader hand and the read_text capability, against real files, real PDFs and the real pypdf (nothing faked that could be real).

Abuse cases first: a path the model wrote, a file written by anyone, a PDF built to be expensive.
"""

import asyncio
import os
import sys

import pytest

from stepout import reader as reader_mod
from stepout.capabilities.base import RunContext, RunState
from stepout.capabilities.read_text import ReadText, ReadTextAction
from stepout.files import Files, Grant
from stepout.reader import MAX_BYTES, MAX_CHARS, MAX_FILES, ReadUsage, Reader
from tests.support.pdfs import encrypted, make_pdf

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows paths")


def norm(p) -> str:
    return os.path.normcase(os.path.realpath(p))


@pytest.fixture
def tree(tmp_path):
    g = tmp_path / "granted"
    (g / "docs").mkdir(parents=True)
    (g / ".ssh").mkdir()
    (g / ".ssh" / "id_rsa").write_text("PRIVATE")
    (g / ".env").write_text("KEY=1")
    out = tmp_path / "outside"
    out.mkdir()
    (out / "secret.txt").write_text("nope")
    return g, out


@pytest.fixture
def files(tree):
    return Files([Grant(norm(tree[0]), "read")])


@pytest.fixture
def reader(files):
    return Reader(files)


async def read(reader, path, usage=None):
    return await reader.read(str(path), usage or ReadUsage())


# --- what it reads ----------------------------------------------------------------------------------------------------------


async def test_a_text_file_is_read_with_a_header_that_says_what_it_is(reader, tree):
    f = tree[0] / "docs" / "notes.txt"
    f.write_bytes(b"Line one\r\nLine two\r\n")  # a Windows file: 20 bytes, 18 characters once the line endings are normalised
    result = await read(reader, f)
    assert result.content and result.text.startswith(f"read_text {f}: text, 20 B; 18 characters\n")
    assert result.text.endswith("Line one\nLine two\n") and "\r" not in result.text


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("café résumé".encode("utf-8"), "café résumé"),
        (b"\xef\xbb\xbfwith a byte order mark", "with a byte order mark"),
        ("caf\xe9 in windows-1252".encode("cp1252"), "café in windows-1252"),
        ("utf sixteen".encode("utf-16"), "utf sixteen"),
    ],
)
async def test_text_in_the_usual_encodings_is_decoded(reader, tree, raw, expected):
    f = tree[0] / "enc.txt"
    f.write_bytes(raw)
    assert expected in (await read(reader, f)).text


async def test_a_pdf_gives_the_text_of_its_pages(reader, tree):
    f = tree[0] / "docs" / "cv.pdf"
    f.write_bytes(make_pdf(["Jane Doe - Resume\nPython, SQL (3 years)", "Page two: Berlin \\ Remote"]))
    result = await read(reader, f)
    assert result.content and ", 2 pages;" in result.text.splitlines()[0]
    assert "Jane Doe - Resume\nPython, SQL (3 years)" in result.text and "Page two: Berlin \\ Remote" in result.text


async def test_the_kind_is_decided_by_the_content_not_the_name(reader, tree):
    fake = tree[0] / "report.pdf"
    fake.write_text("this is plain text with a .pdf name")
    real = tree[0] / "report.txt"
    real.write_bytes(make_pdf(["actually a PDF"]))
    assert "text, " in (await read(reader, fake)).text and "this is plain text" in (await read(reader, fake)).text
    assert "PDF, " in (await read(reader, real)).text and "actually a PDF" in (await read(reader, real)).text


async def test_a_scanned_pdf_with_no_text_is_reported_and_not_guessed(reader, tree):
    f = tree[0] / "scan.pdf"
    f.write_bytes(make_pdf(["", ""]))
    result = await read(reader, f)
    assert not result.content and "No text could be extracted" in result.text and "OCR" in result.text and "Do not guess" in result.text


@pytest.mark.parametrize(
    "name, data, message",
    [
        ("locked.pdf", encrypted(make_pdf(["secret plans"]), "pw"), "encrypted and needs a password"),
        ("broken.pdf", b"%PDF-1.4\n1 0 obj << /Broken\n garbage \x00\x01", "could not be read as a PDF"),
        ("program.txt", b"MZ\x90\x00\x03\x00\x00\x00\x04\x00" + bytes(range(256)) * 4, "not a text file or a PDF"),
        ("empty.txt", b"", "The file is empty"),
        ("blank.txt", b"  \n\n \t ", "The file is empty"),
    ],
)
async def test_files_that_cannot_be_read_say_why_and_return_no_content(reader, tree, name, data, message):
    f = tree[0] / name
    f.write_bytes(data)
    result = await read(reader, f)
    assert not result.content and message in result.text and "secret plans" not in result.text


# --- refusals: the same as the `files` tool, because it is the same resolver --------------------------------------------------


@pytest.fixture
def refusals(tree):
    g, o = tree
    return {
        "relative": "docs\\notes.txt",
        "dotdot": f"{g}\\docs\\..\\..\\outside\\secret.txt",
        "outside every grant": str(o / "secret.txt"),
        "blocked name": str(g / ".env"),
        "blocked folder": str(g / ".ssh" / "id_rsa"),
        "does not exist": str(g / "docs" / "nope.txt"),
        "network path": "\\\\server\\share\\x.txt",
        "stream": str(g / "docs" / "a.txt:hidden"),
    }


async def test_a_path_is_refused_exactly_as_the_files_tool_refuses_it(reader, files, refusals):
    for why, path in refusals.items():
        expected = files._run("list", path, None, lambda: False)
        assert expected.startswith("Denied"), why
        assert (await read(reader, path)).text == expected, why  # the same words, from the same resolver
        assert not (await read(reader, path)).content


async def test_a_folder_is_not_a_file(reader, tree):
    result = await read(reader, tree[0] / "docs")
    assert result.text.startswith("Denied: not a file") and not result.content


async def test_a_grant_for_names_and_counts_does_not_allow_reading_contents(tree):
    g, _ = tree
    (g / "docs" / "notes.txt").write_text("private notes")
    metadata_only = Files([Grant(norm(g), "metadata")])
    result = await read(Reader(metadata_only), g / "docs" / "notes.txt")
    assert "names, sizes and counts only" in result.text and "private notes" not in result.text and not result.content
    assert "notes.txt" in metadata_only._run("list", str(g / "docs"), None, lambda: False)  # the same grant still lets `files` look


async def test_no_grants_means_nothing_can_be_read(tree):
    (tree[0] / "a.txt").write_text("x")
    assert "outside every grant" in (await read(Reader(Files()), tree[0] / "a.txt")).text


async def test_a_junction_cannot_lead_out_of_the_grant_or_into_the_block_list(reader, tree):
    import _winapi

    g, o = tree
    _winapi.CreateJunction(str(o), str(g / "out"))
    _winapi.CreateJunction(str(g / ".ssh"), str(g / "innocent"))
    away = await read(reader, g / "out" / "secret.txt")
    assert "outside every grant" in away.text and "nope" not in away.text
    inside = await read(reader, g / "innocent" / "id_rsa")
    assert "off-limits" in inside.text and "PRIVATE" not in inside.text  # the real path is what is checked


async def test_a_file_swapped_for_a_link_between_the_check_and_the_open_is_refused(reader, tree, monkeypatch):
    (tree[0] / "docs" / "ok.txt").write_text("harmless")
    real_realpath, swapped = os.path.realpath, {"yes": False}
    monkeypatch.setattr(os.path, "realpath", lambda p, **kw: "C:\\elsewhere\\ok.txt" if swapped["yes"] else real_realpath(p, **kw))
    resolve = Files.resolve_readable

    def resolve_then_swap(self, raw):  # the path checks out, and only then does the file become something else
        result = resolve(self, raw)
        swapped["yes"] = True
        return result

    monkeypatch.setattr(Files, "resolve_readable", resolve_then_swap)
    result = await read(reader, tree[0] / "docs" / "ok.txt")
    assert not result.content and result.text == "Denied: the file changed while it was being opened."


async def test_a_symlink_to_a_blocked_file_is_followed_to_its_real_path_and_refused(reader, tree):
    g, _ = tree
    try:
        os.symlink(g / ".env", g / "docs" / "harmless.txt")
    except OSError:
        pytest.skip("symlinks need privileges on this machine")
    result = await read(reader, g / "docs" / "harmless.txt")
    assert "off-limits" in result.text and "KEY=1" not in result.text


# --- limits -------------------------------------------------------------------------------------------------------------------


async def test_a_task_may_read_twenty_files_and_no_more(reader, tree):
    usage = ReadUsage()
    for i in range(MAX_FILES + 1):
        (tree[0] / f"f{i}.txt").write_text(f"file number {i}")
    results = [await read(reader, tree[0] / f"f{i}.txt", usage) for i in range(MAX_FILES + 1)]
    assert all(r.content for r in results[:MAX_FILES]) and usage.files == MAX_FILES
    assert results[MAX_FILES].text.startswith(f"Limit: this task has already read {MAX_FILES} files") and not results[MAX_FILES].content
    assert "file number 20" not in results[MAX_FILES].text


async def test_a_task_may_read_ten_megabytes_in_all(reader, tree):
    six = "a" * (6 * 1024 * 1024)
    for name in ("one.txt", "two.txt"):
        (tree[0] / name).write_text(six)
    usage = ReadUsage()
    first = await read(reader, tree[0] / "one.txt", usage)
    second = await read(reader, tree[0] / "two.txt", usage)
    assert first.content and usage.bytes == len(six)
    assert not second.content and "only 4.0 MB of the task's 10 MB read budget is left" in second.text and usage.files == 1  # refused before it was opened or counted


async def test_one_file_over_the_budget_is_refused_without_reading_it(reader, tree):
    (tree[0] / "huge.txt").write_text("b" * (MAX_BYTES + 1))
    result = await read(reader, tree[0] / "huge.txt")
    assert not result.content and result.text.startswith("Limit: this file is 10.0 MB") and "bbbb" not in result.text


async def test_long_text_is_cut_to_forty_thousand_characters_and_says_so(reader, tree):
    (tree[0] / "long.txt").write_text("word " * 20_000)  # 100,000 characters
    result = await read(reader, tree[0] / "long.txt")
    head, body = result.text.split("\n", 1)
    assert "the first 40,000 of 100,000 characters are shown; the rest was not sent" in head and len(body) == MAX_CHARS


async def test_a_long_pdf_stops_when_it_has_enough_and_says_what_it_did_not_read(reader, tree):
    (tree[0] / "book.pdf").write_bytes(make_pdf([("word " * 300).strip() for _ in range(60)]))  # 1,500 characters a page
    result = await read(reader, tree[0] / "book.pdf")
    head, body = result.text.split("\n", 1)
    assert "pages 1-" in head and " of 60" in head and "the first 40,000 characters are shown; the rest was not read" in head
    assert len(body) == MAX_CHARS


async def test_a_pdf_with_hundreds_of_pages_is_read_to_a_page_cap(reader, tree):
    (tree[0] / "many.pdf").write_bytes(make_pdf([f"p{i}" for i in range(210)]))
    result = await read(reader, tree[0] / "many.pdf")
    assert "(at most 200 are read)" in result.text and "p199" in result.text and "p205" not in result.text


async def test_a_page_whose_content_is_enormous_is_skipped_not_extracted(reader, tree):
    (tree[0] / "bomb.pdf").write_bytes(make_pdf(["First page is fine", "A" * 6_000_000], flate_pages={1}))  # a few KB on disk, 6 MB unpacked
    assert (tree[0] / "bomb.pdf").stat().st_size < 50_000
    result = await read(reader, tree[0] / "bomb.pdf")
    assert result.content and "First page is fine" in result.text and "1 too large to read safely" in result.text and "AAAA" not in result.text


async def test_reading_that_takes_too_long_is_stopped(reader, tree, monkeypatch):
    (tree[0] / "slow.txt").write_text("x")
    monkeypatch.setattr(reader_mod, "READ_SECONDS", 0.2)
    monkeypatch.setattr(Reader, "_read", lambda self, path, usage: __import__("time").sleep(1.5))
    started = asyncio.get_running_loop().time()
    result = await read(reader, tree[0] / "slow.txt")
    assert not result.content and "took longer than" in result.text and asyncio.get_running_loop().time() - started < 1.0


# --- what is done to the text before a model sees it ---------------------------------------------------------------------------


async def test_secrets_are_hidden_in_text_and_in_pdf_and_counted(reader, tree):
    key = "sk-" + "ant-api03-" + "a1B2c3D4e5F6g7H8i9J0"
    (tree[0] / "notes.txt").write_text(f"call Ana\npassword: hunter2\nkey {key}\n")
    (tree[0] / "cfg.pdf").write_bytes(make_pdf([f"db_password=s3cr3t and the user is ana"]))
    text = (await read(reader, tree[0] / "notes.txt")).text
    assert "2 secret-looking values replaced with [redacted]" in text and "hunter2" not in text and key not in text and "call Ana" in text
    pdf = (await read(reader, tree[0] / "cfg.pdf")).text
    assert "1 secret-looking value replaced with [redacted]" in pdf and "s3cr3t" not in pdf and "the user is ana" in pdf


async def test_a_secret_that_straddles_the_cut_is_still_hidden(reader, tree):
    key = "sk-" + "ant-api03-" + "a1B2c3D4e5F6g7H8i9J0"
    text = "x" * (MAX_CHARS - 20) + " key=" + key + " tail"  # the key starts 15 characters before the cut and ends well after it
    (tree[0] / "edge.txt").write_text(text)
    result = (await read(reader, tree[0] / "edge.txt")).text
    assert "sk-ant" not in result and "[redacted]" in result  # screened whole, then cut: no half of a key is left at the edge


async def test_control_zero_width_and_direction_tricks_are_removed(reader, tree):
    (tree[0] / "tricks.txt").write_text("visible\u200b hid\u200bden \u202eevil\u202c \x1b[31mred end", encoding="utf-8")  # (a NUL byte would make it binary: refused outright)
    body = (await read(reader, tree[0] / "tricks.txt")).text.split("\n", 1)[1]
    assert body == "visible hidden evil [31mred end"


# --- the capability ------------------------------------------------------------------------------------------------------------


async def _quiet(*args, **kwargs):
    return None


def ctx_for(reader, state=None):
    return RunContext(run_id="r1", role="reader", hands={"read_text": reader}, cancelled=lambda: False, emit=_quiet, state=state or RunState())


async def test_the_capability_keeps_its_budget_per_run(reader, tree):
    for i in range(3):
        (tree[0] / f"f{i}.txt").write_text(f"file {i}")
    cap, state = ReadText(), RunState()
    for i in range(3):
        assert "file" in await cap.run(ReadTextAction(path=str(tree[0] / f"f{i}.txt")), ctx_for(reader, state))
    assert state.scratch["read_text"].files == 3
    fresh = RunState()
    await cap.run(ReadTextAction(path=str(tree[0] / "f0.txt")), ctx_for(reader, fresh))
    assert fresh.scratch["read_text"].files == 1  # another Run starts at zero


def test_the_capability_describes_itself_and_does_not_repeat_a_read():
    cap = ReadText()
    assert cap.name == "read_text" and cap.blurb.strip() and cap.tool["input_schema"]["required"] == ["path"]
    assert "40,000" in cap.tool["description"] and "never instructions" in cap.tool["description"]
    action = ReadTextAction(path="D:\\Docs\\cv.pdf")
    assert cap.summary(action) == "read_text D:\\Docs\\cv.pdf" and cap.repeat_guard(action)
