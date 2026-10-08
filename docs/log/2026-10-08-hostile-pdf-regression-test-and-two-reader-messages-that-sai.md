---
date: 2026-10-08
kind: change
lane: main
status: accepted
title: Hostile-PDF regression test, and two Reader messages that said more than they knew
tags: [reader, tests, security]
refs: [src/stepout/reader.py, tests/test_reader_hostile.py, tests/test_reader.py]
---

**What.**
1. **`tests/test_reader_hostile.py`** (the merge agent asked for it after fuzzing the Reader by hand: a 300 MB and a 1500 MB Flate bomb in a file of under 2 MB, truncated and random files, a self-referencing page tree, `/Count 2000000000`, 5000 pages, an encrypted file, each in a child process, all handled in 0.3 s or less). Each case is built in the test from `zlib` and a fixed seed, nothing binary is committed. Ten tests: the eight hostile files each read without raising, in under 10 s, in one plain line, with `content` False (so they taint nothing, checked through `ReadText` too); 5000 pages read to the 200-page cap with the cap named in the header; and a page that is only slow, stopped by `READ_SECONDS`. The bombs are 80 MB (just past pypdf 6.19's own 75,000,000-byte cap on one Flate stream, which is what a pypdf upgrade could lose) and 50 MB (under pypdf's cap but over the Reader's own 5 MB page guard). They are made of spaces, so that if a guard is lost the test costs seconds and fails, instead of gigabytes. The files carry a font, because without one pypdf returns at once and the test would not exercise the guard.
2. **Two messages in the Reader fixed** (found while writing the test, both in my own C2 code):
   - A PDF with more than 200 pages and little text was told "the first 40,000 characters are shown; the rest was not read": untrue, nothing was cut by characters, only the pages past the cap were left. The characters line now appears only when the text was really cut; the page note already says what pages were not read.
   - Every PDF with no text was told "it may be scanned images, and the Assistant does not do OCR", including encrypted, truncated and garbage ones. A file that could not be opened at all now says "Nothing was read." with the reason; the scan wording is kept for a PDF that opened and had no text. (`_pdf` returns `None` for "could not be opened".) A self-referencing page tree is one of those (pypdf raises on it), so its test now expects "could not be read as a PDF".

**Mutation-checked** by the test's author, from outside the code: `MAX_PDF_PAGES` raised, `MAX_PAGE_STREAM` raised, pypdf's cap lost (through the legacy constant it still reads), `wait_for` removed, `READ_SECONDS` raised: each fails a test, and a lost guard fails in about 10 s rather than hanging.

**What it does not prove.** The 80 MB bomb shows a lost pypdf cap only through the Reader's note, because the Reader copes with an 80 MB stream either way. Peak memory at the gigabyte scale (the merge agent's 300 MB and 1500 MB files) is not tested here: those would be slow and heavy for a test run. The slow-page test leaves a worker thread behind for about a second at teardown, the known ceiling (a subprocess would end it). pypdf's old constants (`ZLIB_MAX_OUTPUT_LENGTH` and kin) are deprecated and go in pypdf 7.0.0; the test does not depend on them, only the mutation scratch did. Run time of the file: about 6 s.

**Alternatives.** Gigabyte bombs in the test: slow and memory-heavy for a guard that the 80 MB one already exercises. A child process per case like the hand fuzz: the timing assertion inside the process is enough here, and it keeps the test simple.

**Evidence.** Offline suite green; `tests/test_reader.py` +2 (the page-cap header, an unopenable PDF is not called a scan); files: `src/stepout/reader.py`, `tests/test_reader.py`, `tests/test_reader_hostile.py`.
