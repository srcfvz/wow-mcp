from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any


class CborDecodeError(ValueError):
    pass


@dataclass
class _Reader:
    data: bytes
    i: int = 0

    def eof(self) -> bool:
        return self.i >= len(self.data)

    def peek_u8(self) -> int:
        if self.eof():
            raise CborDecodeError("Unexpected end of input")
        return self.data[self.i]

    def read_u8(self) -> int:
        b = self.peek_u8()
        self.i += 1
        return b

    def read(self, n: int) -> bytes:
        if self.i + n > len(self.data):
            raise CborDecodeError("Unexpected end of input")
        out = self.data[self.i : self.i + n]
        self.i += n
        return out


def _read_length(r: _Reader, ai: int) -> int | None:
    if ai < 24:
        return ai
    if ai == 24:
        return r.read_u8()
    if ai == 25:
        return int.from_bytes(r.read(2), "big")
    if ai == 26:
        return int.from_bytes(r.read(4), "big")
    if ai == 27:
        return int.from_bytes(r.read(8), "big")
    if ai == 31:
        return None
    raise CborDecodeError(f"Invalid additional info: {ai}")


def _decode_item(r: _Reader) -> Any:
    initial = r.read_u8()
    major = initial >> 5
    ai = initial & 0x1F

    if major in (0, 1):
        length = _read_length(r, ai)
        if length is None:
            raise CborDecodeError("Indefinite length not allowed for integers")
        if major == 0:
            return length
        return -1 - length

    if major == 2:  # bytes
        length = _read_length(r, ai)
        if length is not None:
            return r.read(length)
        chunks: list[bytes] = []
        while True:
            if r.peek_u8() == 0xFF:
                r.read_u8()
                return b"".join(chunks)
            chunk = _decode_item(r)
            if not isinstance(chunk, (bytes, bytearray)):
                raise CborDecodeError("Indefinite byte string chunk is not bytes")
            chunks.append(bytes(chunk))

    if major == 3:  # text
        length = _read_length(r, ai)
        if length is not None:
            raw = r.read(length)
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.decode("utf-8", errors="replace")
        parts: list[str] = []
        while True:
            if r.peek_u8() == 0xFF:
                r.read_u8()
                return "".join(parts)
            part = _decode_item(r)
            if not isinstance(part, str):
                raise CborDecodeError("Indefinite text string chunk is not text")
            parts.append(part)

    if major == 4:  # array
        length = _read_length(r, ai)
        items: list[Any] = []
        if length is not None:
            for _ in range(length):
                items.append(_decode_item(r))
            return items
        while True:
            if r.peek_u8() == 0xFF:
                r.read_u8()
                return items
            items.append(_decode_item(r))

    if major == 5:  # map
        length = _read_length(r, ai)
        out: dict[Any, Any] = {}
        if length is not None:
            for _ in range(length):
                k = _decode_item(r)
                v = _decode_item(r)
                out[k] = v
            return out
        while True:
            if r.peek_u8() == 0xFF:
                r.read_u8()
                return out
            k = _decode_item(r)
            v = _decode_item(r)
            out[k] = v

    if major == 6:  # tag
        _ = _read_length(r, ai)
        # Ignore tag value and just decode the tagged item.
        return _decode_item(r)

    if major == 7:  # floats / simple
        if ai == 20:
            return False
        if ai == 21:
            return True
        if ai == 22:
            return None
        if ai == 23:
            return None
        if ai == 24:
            return r.read_u8()
        if ai == 25:
            raw = int.from_bytes(r.read(2), "big")
            sign = (raw >> 15) & 0x1
            exp = (raw >> 10) & 0x1F
            frac = raw & 0x3FF
            if exp == 0:
                val = frac * 2 ** (-24)
            elif exp == 31:
                val = float("inf") if frac == 0 else float("nan")
            else:
                val = (1 + frac / 1024) * 2 ** (exp - 15)
            return -val if sign else val
        if ai == 26:
            return struct.unpack(">f", r.read(4))[0]
        if ai == 27:
            return struct.unpack(">d", r.read(8))[0]
        if ai == 31:
            raise CborDecodeError("Unexpected break")
        return None

    raise CborDecodeError(f"Unsupported CBOR major type: {major}")


def loads(data: bytes) -> Any:
    r = _Reader(data=data, i=0)
    value = _decode_item(r)
    if not r.eof():
        # Some producers append trailing NULs; allow pure NUL padding only.
        if any(b != 0 for b in r.data[r.i :]):
            raise CborDecodeError("Trailing data after CBOR payload")
    return value
