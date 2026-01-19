import tempfile
import unittest
from pathlib import Path

from wow_mcp_server.savedvars import LuaParseError, dumps_assignment, load_var, loads_assignments, write_var


class TestSavedVariables(unittest.TestCase):
    def test_loads_assignments_fixture(self) -> None:
        fixture = Path("tests/fixtures/WowMCP_State.lua").read_text(encoding="utf-8")
        assignments = loads_assignments(fixture)

        self.assertIn("WowMCP_State", assignments)
        self.assertIn("WowMCP_Cmd", assignments)
        self.assertIsNone(assignments["WowMCP_Cmd"])

        state = assignments["WowMCP_State"]
        self.assertEqual(state["version"], 1)
        self.assertEqual(state["character"]["name"], "Testy")
        self.assertEqual(state["items"][0]["id"], 6948)  # list coerced from numeric table 1..n
        self.assertEqual(state["note"], "line1\\nline2")

        mixed = state["mixed"]
        self.assertEqual(mixed[1], "a")
        self.assertEqual(mixed[2], "b")
        self.assertEqual(mixed[5], "e")
        self.assertEqual(mixed["key"], "v")

    def test_roundtrip_assignment(self) -> None:
        value = {
            "ok": True,
            "n": 123,
            "s": "a\"b",
            "arr": [1, 2, 3],
            "obj": {"x": 1, "y": False},
        }
        text = dumps_assignment("TestVar", value)
        parsed = loads_assignments(text)["TestVar"]
        self.assertEqual(parsed, value)

    def test_write_var_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "WowMCP_Cmd.lua"
            write_var(p, "WowMCP_Cmd", {"id": "1", "type": "NOTICE", "payload": {"msg": "hi"}})
            self.assertTrue(p.exists())
            self.assertEqual(load_var(p, "WowMCP_Cmd")["payload"]["msg"], "hi")

    def test_reject_bare_identifier_values(self) -> None:
        bad = "X = { foo }"
        with self.assertRaises(LuaParseError):
            loads_assignments(bad)

    def test_numeric_and_hex_string_escapes(self) -> None:
        text = "X = \"A\\000B\\255C\\x7f\""
        parsed = loads_assignments(text)["X"]
        self.assertEqual(parsed[0], "A")
        self.assertEqual(ord(parsed[1]), 0)
        self.assertEqual(parsed[2], "B")
        self.assertEqual(ord(parsed[3]), 255)
        self.assertEqual(parsed[4], "C")
        self.assertEqual(ord(parsed[5]), 0x7F)
