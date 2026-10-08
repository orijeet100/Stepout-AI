"""Secret screening: what is redacted, what is left alone, and that a hostile file cannot make it slow.

Every "secret" here is invented and assembled from pieces, so the repository never holds a string a secret scanner would flag.
"""

import time

import pytest

from stepout.redact import REDACTED, redact

KEY_BODY = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASC" * 3
PRIVATE_KEY = "-----BEGIN " + "PRIVATE KEY-----\n" + KEY_BODY + "\n-----END " + "PRIVATE KEY-----"
RSA_KEY = "-----BEGIN RSA " + "PRIVATE KEY-----\n" + KEY_BODY + "\n-----END RSA " + "PRIVATE KEY-----"
SECRETS = {
    "anthropic key": "sk-" + "ant-api03-" + "a1B2c3D4e5F6g7H8i9J0",
    "other sk- key": "sk-" + "proj-" + "A1b2C3d4E5f6G7h8I9j0K1",
    "aws key id": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
    "aws temporary key id": "AS" + "IA" + "ABCDEFGHIJKLMNOP",
    "github token": "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8",
    "github fine-grained token": "github_" + "pat_" + "11ABCDEFG0abcdefghijkl_mnopqrstuvwxyz",
    "slack token": "xo" + "xb-" + "1234567890-abcdefghijkl",
    "jwt": "ey" + "JhbGciOiJIUzI1NiJ9." + "eyJzdWIiOiIxMjM0NTY3ODkwIn0." + "dBjftJeZ4CVPmB92K27uhbUJU1p1r",
}


@pytest.mark.parametrize("kind", SECRETS)
def test_each_known_secret_shape_is_replaced_in_running_text(kind):
    text, count = redact(f"Contact me. The value is {SECRETS[kind]} (keep it safe) and that is all.")
    assert text == f"Contact me. The value is {REDACTED} (keep it safe) and that is all." and count == 1


def test_a_private_key_block_goes_whole_including_other_key_types():
    text, count = redact(f"before\n{PRIVATE_KEY}\nmiddle\n{RSA_KEY}\nafter")
    assert text == f"before\n{REDACTED}\nmiddle\n{REDACTED}\nafter" and count == 2
    assert KEY_BODY not in text


def test_an_unfinished_private_key_block_takes_everything_after_it():
    text, count = redact("notes\n-----BEGIN " + "PRIVATE KEY-----\n" + KEY_BODY + "\nmore text that follows")
    assert text == f"notes\n{REDACTED}" and count == 1


@pytest.mark.parametrize(
    "line, expected",
    [
        ("password: hunter2", f"password: {REDACTED}"),
        ("Password = 'correct horse battery'", f"Password = {REDACTED}"),
        ("db_password=s3cr3t!", f"db_password={REDACTED}"),  # the usual way secrets appear: a compound name
        ("GITHUB_TOKEN=abc123", f"GITHUB_TOKEN={REDACTED}"),
        ("AWS_SECRET_ACCESS_KEY = abc/123+xyz", f"AWS_SECRET_ACCESS_KEY = {REDACTED}"),
        ("client-secret: abc123", f"client-secret: {REDACTED}"),
        ("accessToken: abc123", f"accessToken: {REDACTED}"),
        ("clientSecret = 'abc 123'", f"clientSecret = {REDACTED}"),
        ('"api_key": "abc123xyz"', f'"api_key": {REDACTED}'),
        ('{"password": "hunter2", "user": "ana"}', f'{{"password": {REDACTED}, "user": "ana"}}'),
        ("API key: abc123xyz", f"API key: {REDACTED}"),
        ("secret=abc, other=1", f"secret={REDACTED}, other=1"),
        ("Token: abcdef123456", f"Token: {REDACTED}"),
        ("passwd:topsecret", f"passwd:{REDACTED}"),
    ],
)
def test_a_labelled_value_loses_the_value_and_keeps_the_label(line, expected):
    assert redact(line) == (expected, 0 if expected == line else 1)


def test_text_that_only_mentions_these_words_is_left_alone():
    prose = (
        "Experience: built a tokenization service and a password reset flow; wrote about secret sharing and API keys in docs. "
        "Skills: sk-learn (not a key), the sk- prefix, AKIA as an acronym, eyJ is how JSON looks in base64. Token economy; secret agent. "
        "Compass: north. Tokenization: 5 years. Passport: kept in the safe. Secret Santa: December 20."
    )
    assert redact(prose) == (prose, 0)


def test_a_label_alone_on_a_line_does_not_take_the_next_line():
    text = "Password:\nSkills: Python, SQL\nToken: \nNext: line"
    assert redact(text) == (text, 0)


def test_a_key_and_its_label_count_once():
    text, count = redact(f"API key: {SECRETS['anthropic key']}")
    assert text == f"API key: {REDACTED}" and count == 1


def test_screening_twice_changes_nothing_the_second_time():
    once, first = redact(f"{PRIVATE_KEY}\npassword: x\n{SECRETS['jwt']}\n{SECRETS['github token']}")
    twice, second = redact(once)
    assert twice == once and first == 4 and second == 0


def test_a_file_made_of_thousands_of_begin_markers_is_screened_fast():
    # A regex that searched ahead from every BEGIN would be quadratic here; the scan is one pass.
    hostile = ("-----BEGIN " + "PRIVATE KEY-----\n") * 200_000
    started = time.perf_counter()
    text, count = redact(hostile)
    assert text == REDACTED and count == 1 and time.perf_counter() - started < 3.0


def test_long_runs_of_name_like_parts_are_screened_in_bounded_time():
    started = time.perf_counter()
    redact("a-" * 21_000 + " " + "a_b." * 10_000 + " token " + "x" * 20_000)  # no label, and a label with a huge name around it
    assert time.perf_counter() - started < 3.0


def test_long_runs_that_look_like_the_start_of_a_token_are_screened_in_bounded_time():
    window = "eyJ" * 14_000  # about the size of what the Reader screens (40,000 characters plus slack)
    started = time.perf_counter()
    redact(window + " " + "sk-" * 14_000 + " " + "a" * 40_000)
    assert time.perf_counter() - started < 3.0
