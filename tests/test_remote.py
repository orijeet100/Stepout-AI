"""`stepout remote`, `status` and the start-up repair against a fake `tailscale`: each state is looked at first and only what is off is repaired,
the link is checked before it is announced, and Funnel is never called (ADR 0020, 0021). Several of these are the failures of the first real run."""

import json
import os
import subprocess

import pytest

from stepout import remote

pytestmark = pytest.mark.skipif(os.name != "nt", reason="`stepout remote` is Windows-only")

HOST = "laptop.tail1234.ts.net"
PHONE = {"HostName": "iphone", "OS": "iOS", "UserID": 7, "Online": True}


def running(host_name="laptop", phone=None):
    peers = {"nodekey:1": phone} if phone else {}
    return {
        "BackendState": "Running",
        "Self": {"HostName": host_name, "DNSName": f"{host_name}.tail1234.ts.net.", "UserID": 7},
        "User": {"7": {"LoginName": "owner@example.com"}},
        "Peer": peers,
    }


class FakeTailscale:
    """`run` for subprocess. `status --json` answers from a list of states (the last repeats); `set --hostname` renames Self after `lag` more
    status reads; `serve --bg` records the handler (or fails with `serve_code`); everything is recorded in `calls`."""

    def __init__(self, *states, serve_code=0, lag=0, handlers=None):
        self.states, self.calls, self.serve_code, self.lag = list(states), [], serve_code, lag
        self.handlers = dict(handlers or {})  # "host:443" -> proxy url
        self.pending = None

    def _state(self):
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        if self.pending and not self.lag:
            state = running(self.pending, (state.get("Peer") or {}).get("nodekey:1"))
            self.states[:] = [state]
            self.pending = None
        elif self.pending:
            self.lag -= 1
        return state

    def __call__(self, argv, **kwargs):
        self.calls.append(argv[1:])
        args = argv[1:]
        if args[:2] == ["status", "--json"]:
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(self._state()))
        if args[:3] == ["serve", "status", "--json"]:
            web = {host: {"Handlers": {"/": {"Proxy": proxy}}} for host, proxy in self.handlers.items()}
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({"Web": web}))
        if args[0] == "set":
            self.pending = args[1].split("=", 1)[1]
        if args[0] == "serve" and args[1] == "--bg" and not self.serve_code:
            dns = (self.states[0].get("Self") or {}).get("DNSName", "").rstrip(".")
            self.handlers[f"{dns}:443"] = args[-1]
        return subprocess.CompletedProcess(argv, self.serve_code if args[0] == "serve" else 0, stdout="")

    def served(self):
        return [c for c in self.calls if c[:2] == ["serve", "--bg"]]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in ("STEPOUT_REMOTE_HOSTS", "STEPOUT_REMOTE_LOGIN"):  # setup writes them to the environment too: put them back afterwards
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)


def go(tmp_path, fake, *, found=("ts",), answers=("",), winget="winget"):
    said, finds, queue = [], list(found), list(answers)
    url = remote.setup(8765, tmp_path / ".env", ask=lambda q: queue.pop(0), out=said.append, run=fake,
                       find=lambda: finds.pop(0) if len(finds) > 1 else finds[0], wait=lambda s: None, winget=lambda: winget)
    return url, said


# ---- setup -----------------------------------------------------------------------------------------------------------


def test_from_nothing_it_installs_with_winget_waits_for_the_sign_in_then_serves_and_records_the_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(remote.platform, "node", lambda: "Orijeet")
    fake = FakeTailscale({"BackendState": "NeedsLogin"}, {"BackendState": "NeedsLogin"}, running("orijeet"))
    url, said = go(tmp_path, fake, found=(None, None, "ts"), answers=("y",))
    assert fake.calls[0][:3] == ["install", "--id", "tailscale.tailscale"]  # winget ran first (the fake records every program's arguments)
    assert any("sign in" in s for s in said)
    env = (tmp_path / ".env").read_text().splitlines()
    assert url == f"https://{fake.states[0]['Self']['DNSName'].rstrip('.')}/"
    assert f"STEPOUT_REMOTE_HOSTS={url[8:-1]}" in env and "STEPOUT_REMOTE_LOGIN=owner@example.com" in env


def test_without_winget_or_with_a_no_it_points_at_the_download_page(tmp_path):
    fake = FakeTailscale(running())
    _, said = go(tmp_path, fake, found=(None, "ts"), winget=None)
    assert any(remote.DOWNLOAD in s for s in said) and not any(c[0] == "install" for c in fake.calls)
    _, said = go(tmp_path, FakeTailscale(running()), found=(None, "ts"), answers=("n",))
    assert any(remote.DOWNLOAD in s for s in said)


def test_the_computers_own_name_is_replaced_by_a_neutral_one_and_serve_waits_for_it(tmp_path, monkeypatch):
    monkeypatch.setattr(remote.platform, "node", lambda: "Orijeet")
    fake = FakeTailscale(running("orijeet"), lag=3)  # the rename reaches Self only after a few reads: Serve must not be keyed to the old name
    url, _ = go(tmp_path, fake)
    renamed = next(c[1].split("=")[1] for c in fake.calls if c[0] == "set")
    assert renamed.startswith("stepout-") and "orijeet" not in renamed
    assert url == f"https://{renamed}.tail1234.ts.net/"
    assert fake.handlers == {f"{renamed}.tail1234.ts.net:443": "http://127.0.0.1:8765"}  # keyed to the new name, not the old
    assert fake.calls.index(["set", f"--hostname={renamed}"]) < fake.calls.index(fake.served()[0])


def test_a_name_already_chosen_is_kept_so_the_phone_link_stays_the_same(tmp_path, monkeypatch):
    monkeypatch.setattr(remote.platform, "node", lambda: "Orijeet")
    fake = FakeTailscale(running("laptop-ori"))
    url, _ = go(tmp_path, fake)
    assert url == "https://laptop-ori.tail1234.ts.net/" and not any(c[0] == "set" for c in fake.calls)


def test_neutral_names_are_unguessable_from_the_computer_name():
    assert remote.neutral_name("Orijeet", "orijeet").startswith("stepout-") and len(remote.neutral_name("Orijeet", "orijeet")) == 12
    assert remote.neutral_name("My PC", "my-pc") is not None  # the slug of the computer's name is what Tailscale defaults to
    assert remote.neutral_name("desk-01", "Orijeet") is None


def test_serve_that_already_points_here_is_left_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(remote.platform, "node", lambda: "other")
    fake = FakeTailscale(running(), handlers={f"{HOST}:443": "http://127.0.0.1:8765"})
    url, _ = go(tmp_path, fake)
    assert url == f"https://{HOST}/" and fake.served() == []  # nothing to repair: no consent page, no reset of anyone's other Serve config


def test_serve_pointing_at_another_port_is_repointed_without_a_reset(tmp_path, monkeypatch):
    monkeypatch.setattr(remote.platform, "node", lambda: "other")
    fake = FakeTailscale(running(), handlers={f"{HOST}:443": "http://127.0.0.1:9999"})
    go(tmp_path, fake)
    assert fake.served() == [["serve", "--bg", "--https=443", "http://127.0.0.1:8765"]]
    assert not any(c[:2] == ["serve", "reset"] for c in fake.calls)


def test_a_failed_serve_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(remote.platform, "node", lambda: "other")
    url, said = go(tmp_path, FakeTailscale(running(), serve_code=1))
    assert url is None and not (tmp_path / ".env").exists() and any("did not start" in s for s in said)


# ---- the check before the link is announced ---------------------------------------------------------------------------


def health(status=200, body='{"app": "stepout", "v": 1}'):
    return lambda url: (status, body)


def test_the_link_is_announced_only_when_it_answers_as_stepout():
    assert remote.verify(HOST, fetch=health(), wait=lambda s: None) is None
    assert "answered 502" in remote.verify(HOST, fetch=health(502, ""), wait=lambda s: None, tries=2)
    assert "answered 200 instead of Stepout" in remote.verify(HOST, fetch=health(200, "<html>"), wait=lambda s: None, tries=2)


def test_a_refusal_is_not_retried_and_says_to_restart():
    calls = []
    problem = remote.verify(HOST, fetch=lambda url: calls.append(url) or (403, ""), wait=lambda s: None)
    assert len(calls) == 1 and "stepout stop" in problem


def test_no_connection_is_retried_then_reported():
    def refuse(url):
        raise OSError("name not resolved")

    seen = []
    problem = remote.verify(HOST, fetch=refuse, wait=seen.append, tries=3)
    assert "could not open" in problem and len(seen) == 2  # waited between tries, not after the last


def test_a_certificate_that_arrives_late_still_gets_through():
    answers = iter([OSError("tls"), OSError("tls"), (200, '{"app": "stepout"}')])

    def late(url):
        a = next(answers)
        if isinstance(a, Exception):
            raise a
        return a

    assert remote.verify(HOST, fetch=late, wait=lambda s: None) is None


# ---- the repair at every start ----------------------------------------------------------------------------------------


def test_prepare_repairs_a_missing_serve_then_checks_the_address():
    fake = FakeTailscale(running())
    assert remote.prepare(8765, HOST, run=fake, find=lambda: "ts", fetch=health(), wait=lambda s: None) is None
    assert fake.served() == [["serve", "--bg", "--https=443", "http://127.0.0.1:8765"]]


def test_prepare_says_what_is_wrong_in_order():
    assert "not installed" in remote.prepare(8765, HOST, find=lambda: None)
    assert "sign in" in remote.prepare(8765, HOST, run=FakeTailscale({"BackendState": "NeedsLogin"}), find=lambda: "ts")
    renamed = remote.prepare(8765, HOST, run=FakeTailscale(running("other")), find=lambda: "ts")
    assert "other.tail1234.ts.net" in renamed and "stepout remote" in renamed
    assert "could not be turned on" in remote.prepare(8765, HOST, run=FakeTailscale(running(), serve_code=1), find=lambda: "ts")


# ---- stepout status, the phone half -----------------------------------------------------------------------------------


def rows(fake, host=HOST, fetch=health()):
    return remote.report(8765, host, run=fake, find=lambda: "ts", fetch=fetch)


def test_status_all_good():
    fake = FakeTailscale(running(phone=PHONE), handlers={f"{HOST}:443": "http://127.0.0.1:8765"})
    assert all(ok for ok, _ in rows(fake))


def test_status_names_the_part_that_is_off():
    offline = {**PHONE, "Online": False}
    fake = FakeTailscale(running(phone=offline), handlers={})
    text = " | ".join(line for ok, line in rows(fake) if not ok)
    assert "Serve is not forwarding" in text and "offline: open the Tailscale app" in text
    assert "No phone" in " | ".join(line for _, line in rows(FakeTailscale(running())))


def test_a_phone_that_calls_itself_localhost_is_named_by_its_system():
    fake = FakeTailscale(running(phone={**PHONE, "HostName": "localhost", "Online": False}))
    assert "Phone (iOS) is offline" in " | ".join(line for _, line in rows(fake))


def test_status_when_phone_access_was_never_set_up_is_information_not_a_fault():
    assert remote.report(8765, "") == [(None, "Phone access is not set up (`stepout remote` sets it up).")]


def test_status_when_the_address_does_not_answer():
    def refuse(url):
        raise OSError("refused")

    fake = FakeTailscale(running(phone=PHONE), handlers={f"{HOST}:443": "http://127.0.0.1:8765"})
    assert rows(fake, fetch=refuse)[-1][0] is False


# ---- off, and no Funnel -----------------------------------------------------------------------------------------------


def test_off_stops_serving_and_forgets_the_remote_settings(tmp_path):
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=k\nSTEPOUT_REMOTE_HOSTS=a.ts.net\nSTEPOUT_REMOTE_LOGIN=o@x\n")
    fake = FakeTailscale(running())
    remote.off(tmp_path / ".env", run=fake, find=lambda: "ts", out=lambda s: None)
    assert ["serve", "--https=443", "off"] in fake.calls
    assert (tmp_path / ".env").read_text() == "ANTHROPIC_API_KEY=k\n"


def test_funnel_is_never_called(tmp_path, monkeypatch):
    monkeypatch.setattr(remote.platform, "node", lambda: "Orijeet")
    fake = FakeTailscale(running("orijeet"))
    go(tmp_path, fake)
    remote.prepare(8765, HOST, run=fake, find=lambda: "ts", fetch=health(), wait=lambda s: None)
    remote.off(tmp_path / ".env", run=fake, find=lambda: "ts", out=lambda s: None)
    assert not any("funnel" in arg for call in fake.calls for arg in call)
    source = open(remote.__file__, encoding="utf-8").read()
    assert '"funnel"' not in source and "'funnel'" not in source
