from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
from typing import Any


class LuaParseError(ValueError):
    pass


_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER_RE = re.compile(r"-?(?:0x[0-9A-Fa-f]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)")
_HEX_DIGIT_RE = re.compile(r"[0-9A-Fa-f]")


def _escape_lua_string(value: str) -> str:
    value = value.replace("\\", "\\\\")
    value = value.replace("\"", "\\\"")
    value = value.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return value


def dumps_lua(value: Any) -> str:
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return f"\"{_escape_lua_string(value)}\""
    if isinstance(value, list):
        inner = ", ".join(dumps_lua(v) for v in value)
        return "{ " + inner + " }"
    if isinstance(value, dict):
        items: list[str] = []

        def key_sort_key(k: Any) -> tuple[int, str]:
            if isinstance(k, int):
                return (0, f"{k:020d}")
            return (1, str(k))

        for key in sorted(value.keys(), key=key_sort_key):
            v = value[key]
            if isinstance(key, str) and _IDENT_RE.fullmatch(key):
                items.append(f"{key} = {dumps_lua(v)}")
            elif isinstance(key, int):
                items.append(f"[{key}] = {dumps_lua(v)}")
            else:
                items.append(f"[{dumps_lua(key)}] = {dumps_lua(v)}")

        return "{ " + ", ".join(items) + " }"

    raise TypeError(f"Unsupported type for Lua dump: {type(value).__name__}")


def dumps_assignment(var_name: str, value: Any) -> str:
    if not _IDENT_RE.fullmatch(var_name):
        raise ValueError(f"Invalid Lua global name: {var_name!r}")
    return f"{var_name} = {dumps_lua(value)}\n"


def _maybe_table_to_list(table: dict[Any, Any]) -> dict[Any, Any] | list[Any]:
    if not table:
        return {}
    if not all(isinstance(k, int) for k in table.keys()):
        return table
    max_key = max(table.keys())
    if max_key <= 0:
        return table
    for i in range(1, max_key + 1):
        if i not in table:
            return table
    return [table[i] for i in range(1, max_key + 1)]


@dataclass
class _Parser:
    s: str
    i: int = 0

    def eof(self) -> bool:
        return self.i >= len(self.s)

    def peek(self) -> str:
        if self.eof():
            return ""
        return self.s[self.i]

    def _starts_with(self, prefix: str) -> bool:
        return self.s.startswith(prefix, self.i)

    def consume(self, expected: str | None = None) -> str:
        if self.eof():
            raise LuaParseError("Unexpected end of input")
        ch = self.s[self.i]
        if expected is not None and ch != expected:
            raise LuaParseError(f"Expected {expected!r} but got {ch!r} at {self.i}")
        self.i += 1
        return ch

    def skip_ws_and_comments(self) -> None:
        while True:
            while not self.eof() and self.peek().isspace():
                self.i += 1

            if self._starts_with("--[["):
                self.i += 4
                end = self.s.find("]]", self.i)
                if end == -1:
                    self.i = len(self.s)
                    return
                self.i = end + 2
                continue

            if self._starts_with("--"):
                end = self.s.find("\n", self.i)
                if end == -1:
                    self.i = len(self.s)
                    return
                self.i = end + 1
                continue

            return

    def parse_identifier(self) -> str:
        self.skip_ws_and_comments()
        m = _IDENT_RE.match(self.s, self.i)
        if not m:
            raise LuaParseError(f"Expected identifier at {self.i}")
        self.i = m.end()
        return m.group(0)

    def parse_number(self) -> int | float:
        self.skip_ws_and_comments()
        m = _NUMBER_RE.match(self.s, self.i)
        if not m:
            raise LuaParseError(f"Expected number at {self.i}")
        token = m.group(0)
        self.i = m.end()
        if token.lower().startswith("-0x") or token.lower().startswith("0x"):
            return int(token, 16)
        if "." in token or "e" in token.lower():
            return float(token)
        return int(token)

    def parse_string(self) -> str:
        self.skip_ws_and_comments()
        quote = self.peek()
        if quote not in ("\"", "'"):
            raise LuaParseError(f"Expected string at {self.i}")
        self.consume()

        out: list[str] = []
        while not self.eof():
            ch = self.consume()
            if ch == quote:
                return "".join(out)
            if ch != "\\":
                out.append(ch)
                continue

            if self.eof():
                raise LuaParseError("Unterminated escape sequence")
            esc = self.consume()

            # Lua numeric escape sequences: \ddd (1-3 digits) and \xHH
            if esc.isdigit():
                digits = esc
                for _ in range(2):
                    if not self.eof() and self.peek().isdigit():
                        digits += self.consume()
                    else:
                        break
                out.append(chr(int(digits, 10) & 0xFF))
                continue

            if esc == "x":
                if self.eof():
                    raise LuaParseError("Unterminated hex escape")
                a = self.consume()
                if self.eof():
                    raise LuaParseError("Unterminated hex escape")
                b = self.consume()
                if not _HEX_DIGIT_RE.fullmatch(a) or not _HEX_DIGIT_RE.fullmatch(b):
                    raise LuaParseError(f"Invalid hex escape at {self.i}")
                out.append(chr(int(a + b, 16)))
                continue

            match esc:
                case "n":
                    out.append("\n")
                case "r":
                    out.append("\r")
                case "t":
                    out.append("\t")
                case "\\":
                    out.append("\\")
                case "\"":
                    out.append("\"")
                case "'":
                    out.append("'")
                case _:
                    out.append(esc)

        raise LuaParseError("Unterminated string literal")

    def parse_value(self) -> Any:
        self.skip_ws_and_comments()
        ch = self.peek()
        if ch == "{":
            return self.parse_table()
        if ch in ("\"", "'"):
            return self.parse_string()
        if ch.isdigit() or ch == "-":
            return self.parse_number()
        if ch.isalpha() or ch == "_":
            ident = self.parse_identifier()
            if ident == "true":
                return True
            if ident == "false":
                return False
            if ident == "nil":
                return None
            raise LuaParseError(f"Unexpected bare identifier value: {ident!r}")
        raise LuaParseError(f"Unexpected token {ch!r} at {self.i}")

    def parse_table(self) -> Any:
        self.skip_ws_and_comments()
        self.consume("{")

        table: dict[Any, Any] = {}
        next_index = 1

        while True:
            self.skip_ws_and_comments()
            if self.peek() == "}":
                self.consume("}")
                return _maybe_table_to_list(table)

            if self.peek() == "[":
                self.consume("[")
                key = self.parse_value()
                self.skip_ws_and_comments()
                self.consume("]")
                self.skip_ws_and_comments()
                self.consume("=")
                value = self.parse_value()
                table[key] = value
            else:
                # identifier = value  OR  bare value
                if self.peek().isalpha() or self.peek() == "_":
                    start = self.i
                    ident = self.parse_identifier()
                    self.skip_ws_and_comments()
                    if self.peek() == "=":
                        self.consume("=")
                        value = self.parse_value()
                        table[ident] = value
                    else:
                        self.i = start
                        value = self.parse_value()
                        while next_index in table:
                            next_index += 1
                        table[next_index] = value
                        next_index += 1
                else:
                    value = self.parse_value()
                    while next_index in table:
                        next_index += 1
                    table[next_index] = value
                    next_index += 1

            self.skip_ws_and_comments()
            if self.peek() in (",", ";"):
                self.consume()
                continue


def loads_assignments(text: str) -> dict[str, Any]:
    p = _Parser(text)
    assignments: dict[str, Any] = {}
    while True:
        p.skip_ws_and_comments()
        if p.eof():
            return assignments
        name = p.parse_identifier()
        p.skip_ws_and_comments()
        p.consume("=")
        value = p.parse_value()
        assignments[name] = value
        p.skip_ws_and_comments()
        if p.peek() in (";", ","):
            p.consume()


def load_var(path: Path, var_name: str) -> Any:
    # SavedVariables can contain binary-ish strings (e.g., CBOR blobs) which are not
    # guaranteed to be valid UTF-8. Using latin-1 preserves byte values 0x00-0xFF.
    text = path.read_bytes().decode("latin-1")
    assignments = loads_assignments(text)
    if var_name not in assignments:
        raise KeyError(f"Variable {var_name!r} not found in {path}")
    return assignments[var_name]


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def write_var(path: Path, var_name: str, value: Any) -> None:
    atomic_write_text(path, dumps_assignment(var_name, value))
