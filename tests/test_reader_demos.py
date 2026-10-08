"""The two Reader demos, offline: a scripted model plays the Orchestrator and the specialists, everything else is real.

Real Files hand over a real folder (invented names), real PDFs generated in the test and read by the real pypdf, the real Gate and Runner.
Demo A: "Summarize the newest PDF in <folder>". Demo B: "Compare my resume in <folder> to the job posting at <URL>".
What the model would decide is for the live check (the merge agent); these pin what the code does with those decisions.
"""

import os
import time

from stepout.capabilities.read_text import ReadTextAction
from stepout.domain import FilesAction
from stepout.files import Files, Grant
from stepout.model import ModelResponse
from stepout.roles import ROLES
from tests.support.pdfs import make_pdf
from tests.test_runner import FakeBrowser, Harness, browse, delegate, plan, say


def norm(p) -> str:
    return os.path.normcase(os.path.realpath(p))


def reads(path):
    return ModelResponse(action=ReadTextAction(path=str(path)), cost_usd=0.001)


def finds(folder, pattern):
    return ModelResponse(action=FilesAction(op="find", path=str(folder), pattern=pattern), cost_usd=0.001)


def at(path, iso):
    stamp = time.mktime(time.strptime(iso, "%Y-%m-%d"))
    os.utime(path, (stamp, stamp))


def actions(h, task):
    """(role, action kind, verdict) of every step in the Run, in order."""
    return [(e.role, e.data["action"]["kind"], e.data["verdict"]) for e in h.ledger.query(task.id) if e.kind == "step"]


def test_the_orchestrator_is_told_not_to_plan_a_reader_step_before_it_has_the_path():
    system = ROLES["orchestrator"].system
    assert "do NOT plan the reader step yet" in system and "Never plan a files step and a reader step in the same plan" in system


async def test_demo_a_summarize_the_newest_pdf_in_a_folder(tmp_path):
    folder = tmp_path / "Reports"
    folder.mkdir()
    old, new = folder / "old-report.pdf", folder / "new-report.pdf"
    old.write_bytes(make_pdf(["Q1 report: revenue flat, hiring paused."]))
    new.write_bytes(make_pdf(["Q3 report: revenue up 12 percent.\nThree new customers signed.", "Outlook: expand to two regions."]))
    (folder / "notes.txt").write_text("meeting notes, not a pdf")
    at(old, "2026-01-05")
    at(new, "2026-09-20")

    script = [
        plan(f"find the newest PDF in {folder}", role="files"),  # 0 the Orchestrator plans the first part; the Files agent starts
        finds(folder, "pdf"),  # 1
        say(f"The newest PDF is {new}."),  # 2
        plan(f"read {new} and summarize it", role="reader"),  # 3 re-plan, now the path is known; the Reader starts
        reads(new),  # 4
        say("Q3: revenue up 12 percent, three new customers, plans to expand to two regions."),  # 5
        say("Your newest PDF, new-report.pdf (20 Sep), says revenue rose 12 percent in Q3 and the company plans two new regions."),  # 6
    ]
    h = Harness(tmp_path, script, files=Files([Grant(norm(folder), "read")]))
    task = await h.run(f"Summarize the newest PDF in {folder}")

    found = h.seen_by(2)  # what the Files agent saw: the real `find`, newest first
    assert found.index("new-report.pdf") < found.index("old-report.pdf") and "notes.txt" not in found
    assert str(new) in h.seen_by(3)  # the Orchestrator read the path in the Finding when it re-planned
    reader_view = h.seen_by(5)
    assert "Q3 report: revenue up 12 percent." in reader_view and "Outlook: expand to two regions." in reader_view  # both pages of the newest PDF
    assert "Q1 report" not in reader_view and "hiring paused" not in h.seen_by(6)  # the older one was never read
    assert actions(h, task) == [
        ("orchestrator", "plan", "allow"), ("files", "files", "allow"), ("files", "answer", "allow"),
        ("orchestrator", "plan", "allow"), ("reader", "read_text", "allow"), ("reader", "answer", "allow"), ("orchestrator", "answer", "allow"),
    ]
    assert h.replies[0].text.startswith("Your newest PDF, new-report.pdf") and "12 percent" in h.replies[0].text
    assert len(h.model.requests) == 7  # the cheapest honest flow: two plans, no Reader step spent before the path was known


async def test_demo_b_compare_my_resume_to_the_job_posting_reading_the_web_first_and_the_file_last(tmp_path):
    folder = tmp_path / "Career"
    folder.mkdir()
    resume = folder / "resume-ana-quinn.pdf"
    resume.write_bytes(make_pdf(["Ana Quinn - Data Engineer\nPython, SQL, Airflow (5 years)\nNo Kubernetes experience."]))
    url = "https://jobs.example.com/data-engineer"
    posting = ("URL: https://jobs.example.com/data-engineer\nTitle: Data Engineer\nText: Wanted: Python, SQL, 3+ years, Kubernetes a plus.", "abc/1.jpg")
    browser = FakeBrowser(posting)

    script = [
        plan(f"open {url} and list what the job asks for", role="browser"),  # 0 web first
        browse("open", url),  # 1 allowed: nothing has been read yet
        say("The posting asks for Python, SQL, 3+ years; Kubernetes is a plus."),  # 2
        plan(f"find the resume in {folder}", role="files"),  # 3 the path is needed: plan the next part
        finds(folder, "resume"),  # 4
        say(f"The resume is {resume}."),  # 5
        plan(f"read {resume} and list its skills and years", role="reader"),  # 6 reading last
        reads(resume),  # 7
        say("Python, SQL, Airflow, 5 years; no Kubernetes."),  # 8
        say("You match Python and SQL with 5 years against 3+ asked. Kubernetes is a plus and your resume has none: worth saying you are learning it."),  # 9
    ]
    h = Harness(tmp_path, script, files=Files([Grant(norm(folder), "read")]), browser=browser)
    task = await h.run(f"Compare my resume in {folder} to the job posting at {url}")

    kinds = [(role, kind) for role, kind, verdict in actions(h, task) if role != "orchestrator"]
    assert kinds == [("browser", "browse"), ("browser", "answer"), ("files", "files"), ("files", "answer"), ("reader", "read_text"), ("reader", "answer")]
    assert not [1 for _, _, verdict in actions(h, task) if verdict != "allow"]  # nothing was refused: the order was the right one
    assert browser.calls[0][1:] == ("open", url, None)  # the posting was opened (before the resume was read)
    assert "Ana Quinn - Data Engineer" in h.seen_by(8) and "No Kubernetes experience." in h.seen_by(8)  # the Reader saw the whole resume
    final = h.seen_by(9)  # the Orchestrator holds both Findings
    assert "Kubernetes is a plus" in final and "no Kubernetes" in final
    assert h.replies[0].text.startswith("You match Python and SQL")
    assert len(h.model.requests) == 10  # three plans (the ceiling), two calls per specialist, the answer


async def test_demo_b_in_the_wrong_order_the_posting_is_refused_and_the_answer_says_so(tmp_path):
    folder = tmp_path / "Career"
    folder.mkdir()
    resume = folder / "resume-ana-quinn.pdf"
    resume.write_bytes(make_pdf(["Ana Quinn - Data Engineer\nPython, SQL, Airflow (5 years)"]))
    browser = FakeBrowser(("URL: https://jobs.example.com/x\nTitle: Job\nText: ...", None))
    script = [
        plan(f"read {resume}", role="reader"),  # reading first: this closes the web
        reads(resume),
        say("Python, SQL, Airflow, 5 years."),
        plan("open the posting at https://jobs.example.com/x", role="browser"),
        browse("open", "https://jobs.example.com/x"),  # refused by the Gate
        say("I could not open the posting: the web is closed after reading a file."),
        say("I read your resume (Python, SQL, Airflow, 5 years) but could not open the job posting, so I cannot compare them. Ask me again with the posting first."),
    ]
    h = Harness(tmp_path, script, files=Files([Grant(norm(folder), "read")]), browser=browser)
    task = await h.run("Compare my resume to the job posting")
    assert browser.calls == [] and ("browser", "browse", "refuse") in actions(h, task)  # the page was never opened
    assert "the web is closed" in h.seen_by(5) and h.replies[0].text.startswith("I read your resume")
