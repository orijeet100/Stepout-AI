"""The offline half of scripts/acceptance.py: what the model decides, as one short script per query, and the pages the fake hands serve.

The scripts only decide (plan, which hand, which path). The answers are made from what the real hands returned (the Files walk, the Reader over
real PDFs), so the counts and the PDF facts in an answer are real; if a hand breaks, the check fails, not the script. Order is call order:
the front door's screening call first, then the Orchestrator's and the specialists' calls (a plan runs its first step itself).
"""

from __future__ import annotations

import os
import re

from tests.support.scripted_model import ScriptedModel
from tests.test_front_door import proceed, screened
from tests.test_reader_demos import reads
from tests.test_runner import FakeBrowser, FakeFetcher, browse, fetch, looks, plan, say

NEWS_URL = "https://news.example.com/new-york"
NEWS_TEXT = "Subway service was restored after an overnight outage. Free concerts return to Central Park this weekend."
COMPANY_URL = "https://fernhollow.example.com/"


def posting_page(url: str):
    return (f"URL: {url}\nTitle: Data Engineer\nText: Wanted: Python, SQL, 3+ years. Kubernetes is a plus.", None)


class Script(ScriptedModel):
    """A ScriptedModel whose steps may be functions of the request: they answer from what the request holds (the hand's result)."""

    async def call(self, request):
        step = await super().call(request)
        return step(request) if callable(step) else step


def _notes(request) -> str:
    """What a Role has learned so far (its notes), without the Task line and the closing nudge."""
    return request.user_text.split("\n\n", 1)[1].rsplit("\n\nThe results of your calls", 1)[0]


def _findings(request) -> list[str]:
    """The Findings an Orchestrator holds, oldest first."""
    return [f.strip() for f in re.split(r"Finding for step \d+ \(\w+\):\n", _notes(request))[1:]]


def hand_result(request):
    """A specialist's Finding: what its hand returned."""
    return say(_notes(request))


def page_one(request):
    """The Reader's Finding: the first page of the file it read (a summary rests on it; page two is where the planted instruction sits)."""
    return say(_notes(request).split("\n", 1)[1].split("\n\n")[0])


def last_finding(request):
    return say(_findings(request)[-1])


def compare(request):
    found = _findings(request)
    return say(f"The posting:\n{found[0]}\n\nYour resume:\n{found[-1]}")


def scripts(folder: str, url: str) -> dict[str, list]:
    new, resume = os.path.join(folder, "new-report.pdf"), os.path.join(folder, "resume-rowan-fields.pdf")
    return {
        "m1": [proceed(), plan("find today's news in New York", role="direct"), fetch(NEWS_URL), hand_result, last_finding],
        "m2": [proceed(), plan(f"count the files in {folder} by type", role="files"), looks("count", folder), hand_result, last_finding],
        "m3": [proceed(), plan(f"open {url} and report the job title and the skills", role="browser"), browse("open", url), hand_result, last_finding],
        "m4a": [
            proceed(),
            plan(f"find the newest PDF in {folder}", role="files"), looks("find", folder, "pdf"), hand_result,
            plan(f"read {new} and summarize it", role="reader"), reads(new), page_one,
            last_finding,
        ],
        "m4b": [
            proceed(),
            plan(f"open {url} and list what the job asks for", role="browser"), browse("open", url), hand_result,  # the web first
            plan(f"find the resume in {folder}", role="files"), looks("find", folder, "resume"), hand_result,
            plan(f"read {resume} and list its skills", role="reader"), reads(resume), page_one,  # the file last
            compare,
        ],
        "follow-up": [  # the front door links it to the first answer in the chat, which read a file; the Orchestrator tries the web anyway
            proceed(1),
            plan("open the company's website", role="browser"), browse("open", COMPANY_URL), hand_result,
            last_finding,
        ],
        "decline": [screened(decision="decline", reply="That would delete your files.", alternative="I can list and count them.", related=[])],
        "chat": [screened(decision="chat", chat_kind="thanks", reply="You're welcome!", related=[])],
    }


def world(ids: list[str], folder: str, url: str):
    """-> (model, fetcher, browser) for these queries, run in this order."""
    table = scripts(folder, url)
    return Script([step for i in ids for step in table[i]]), FakeFetcher(NEWS_TEXT), FakeBrowser(*[posting_page(url)] * 5)
