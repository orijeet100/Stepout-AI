from datetime import datetime, timezone

from stepout.memory import commands
from stepout.memory import MemoryService, NullMemory
from stepout.memory.files import FileStore
from stepout.memory.persona import Persona

NOW = datetime(2026, 10, 12, tzinfo=timezone.utc)


def service(tmp_path):
    return MemoryService(Persona(tmp_path / "persona.md"), FileStore(tmp_path / "learned.jsonl"))


async def test_remember_keeps_a_line_in_persona_and_says_where(tmp_path):
    memory = service(tmp_path)
    said = await commands.handle("remember", "I keep my CV in D:\\Career", memory)
    assert said.startswith("Kept in your Persona as `p-") and "D:\\Career" in said
    assert (tmp_path / "persona.md").read_text(encoding="utf-8") == "- I keep my CV in D:\\Career\n"


async def test_memory_lists_everything_with_ids_and_where_each_came_from(tmp_path):
    memory = service(tmp_path)
    await commands.handle("remember", "I live in Oslo", memory)
    await memory.learn(["I have a dog"], conversation_id="c1", message_at=NOW)
    said = await commands.handle("memory", "", memory)
    assert "**Persona (a line you wrote)**" in said and "I live in Oslo" in said
    assert "**Learned from what you said**" in said and "I have a dog (you said it on 2026-10-12)" in said
    assert "`/forget <id>`" in said


async def test_an_empty_memory_says_how_to_start(tmp_path):
    assert "/remember" in await commands.handle("memory", "", service(tmp_path))


async def test_forget_removes_exactly_one_entry_by_id_or_by_a_unique_start_of_it(tmp_path):
    memory = service(tmp_path)
    (a, b) = await memory.learn(["I have a dog", "I like tea"], conversation_id="c1", message_at=NOW)
    said = await commands.handle("forget", a.id, memory)
    assert said == f"Forgot `{a.id}`: I have a dog"
    said = await commands.handle("forget", b.id[:4], memory)  # "f-xx": more than one could start so, but only b is left
    assert said.startswith("Forgot") and await memory.entries() == []


async def test_forget_with_an_unknown_or_ambiguous_id_removes_nothing(tmp_path):
    memory = service(tmp_path)
    await memory.learn(["I have a dog", "I like tea"], conversation_id="c1", message_at=NOW)
    assert "Nothing is kept under `f-zzzz`" in await commands.handle("forget", "f-zzzz", memory)
    said = await commands.handle("forget", "f-", memory)  # both start so
    assert said.startswith("More than one matches") and len(await memory.entries()) == 2


async def test_a_command_without_what_it_needs_says_what_it_needs(tmp_path):
    memory = service(tmp_path)
    assert "/remember" in await commands.handle("remember", "  ", memory)
    assert "/forget <id>" in await commands.handle("forget", "", memory)


async def test_with_memory_off_the_commands_say_so():
    for name in ("remember", "memory", "forget"):
        assert "Memory is off" in await commands.handle(name, "x", NullMemory())


async def test_a_command_that_is_not_ours_is_left_to_the_caller(tmp_path):
    assert await commands.handle("dance", "", service(tmp_path)) is None
