"""The terminal channel has no cost field to show, so it prints the cost under a reply that has one."""

from stepout.channels.cli import CliChannel
from stepout.domain import Reply


async def test_a_reply_with_a_cost_shows_it_under_the_text(capsys):
    await CliChannel().send(Reply(text="Paris", cost_usd=0.0027))
    assert capsys.readouterr().out == "Paris\n\n(cost: $0.0027)\n"


async def test_a_reply_without_a_cost_is_just_its_text(capsys):
    channel = CliChannel()
    await channel.send(Reply(text="Unknown command: /x"))  # no Run, no model call
    await channel.send(Reply(text="hello", cost_usd=0.0))  # a front door that cost nothing
    assert capsys.readouterr().out == "Unknown command: /x\nhello\n"
