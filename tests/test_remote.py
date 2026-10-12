"""`stepout remote` against a fake `tailscale`: each state prints the next step and waits; Funnel is never called (ADR 0020)."""

import json
import os
import subprocess

import pytest

from stepout import remote

pytestmark = pytest.mark.skipif(os.name != "nt", reason="`stepout remote` is Windows-only")

RUNNING = {
    "BackendState": "Running",
    "Self": {"HostName": "laptop", "DNSName": "laptop.tail1234.ts.net.", "UserID": 7},
    "User": {"7": {"LoginName": "owner@example.com"}},
}


class FakeTailscale:
    """`run` for subprocess: answers `status --json` from a list of states (the last repeats) and records every call."""

    def __init__(self, *states, serve_code=0):
        self.states, self.calls, self.serve_code = list(states), [], serve_code

    def __call__(self, argv, **kwargs):
        self.calls.append(argv[1:])
        if argv[1:3] == ["status", "--json"]:
            state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(state))
        return subprocess.CompletedProcess(argv, self.serve_code if argv[1] == "serve" else 0, stdout="")


@pytest.fixture(autouse=True)
def no_qr(monkeypatch):
    monkeypatch.setattr(remote, "show_qr", lambda url: None)
    for name in ("STEPOUT_REMOTE_HOSTS", "STEPOUT_REMOTE_LOGIN"):  # setup writes them to the environment too: put them back afterwards
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)


def go(tmp_path, fake, *, found=("ts",), names=("",)):
    said, finds = [], list(found)
    url = remote.setup(8765, tmp_path / ".env", ask=lambda q: names[0], out=said.append, run=fake,
                       find=lambda: finds.pop(0) if len(finds) > 1 else finds[0], wait=lambda s: None)
    return url, said


def test_from_nothing_it_waits_for_the_install_and_the_sign_in_then_serves_and_records_the_owner(tmp_path, monkeypatch):
    fake = FakeTailscale({"BackendState": "NeedsLogin"}, {"BackendState": "NeedsLogin"}, RUNNING)
    url, said = go(tmp_path, fake, found=(None, None, "ts"))
    assert url == "https://laptop.tail1234.ts.net/"
    assert any("winget install tailscale.tailscale" in s for s in said) and any("sign in" in s for s in said)
    assert ["serve", "--bg", "--https=443", "http://127.0.0.1:8765"] in fake.calls
    env = (tmp_path / ".env").read_text().splitlines()
    assert "STEPOUT_REMOTE_HOSTS=laptop.tail1234.ts.net" in env and "STEPOUT_REMOTE_LOGIN=owner@example.com" in env


def test_a_new_name_is_set_before_serving(tmp_path, monkeypatch):
    fake = FakeTailscale(RUNNING)
    go(tmp_path, fake, names=("desk-01",))
    assert fake.calls.index(["set", "--hostname=desk-01"]) < next(i for i, c in enumerate(fake.calls) if c[0] == "serve")


def test_a_failed_serve_writes_nothing(tmp_path):
    url, said = go(tmp_path, FakeTailscale(RUNNING, serve_code=1))
    assert url is None and not (tmp_path / ".env").exists() and any("did not start" in s for s in said)


def test_off_stops_serving_and_forgets_the_remote_settings(tmp_path):
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=k\nSTEPOUT_REMOTE_HOSTS=a.ts.net\nSTEPOUT_REMOTE_LOGIN=o@x\n")
    fake = FakeTailscale(RUNNING)
    remote.off(tmp_path / ".env", run=fake, find=lambda: "ts", out=lambda s: None)
    assert ["serve", "--https=443", "off"] in fake.calls
    assert (tmp_path / ".env").read_text() == "ANTHROPIC_API_KEY=k\n"


def test_funnel_is_never_called(tmp_path, monkeypatch):
    fake = FakeTailscale(RUNNING)
    go(tmp_path, fake)
    remote.off(tmp_path / ".env", run=fake, find=lambda: "ts", out=lambda s: None)
    assert not any("funnel" in arg for call in fake.calls for arg in call)
    source = open(remote.__file__, encoding="utf-8").read()
    assert '"funnel"' not in source and "'funnel'" not in source
