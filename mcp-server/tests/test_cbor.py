import unittest

from wow_mcp_server.cbor import CborDecodeError, loads


class TestCbor(unittest.TestCase):
    def test_basic_map(self) -> None:
        # {"a": 1, "b": [2, 3]}
        payload = bytes([0xA2, 0x61, 0x61, 0x01, 0x61, 0x62, 0x82, 0x02, 0x03])
        self.assertEqual(loads(payload), {"a": 1, "b": [2, 3]})

    def test_negative_int(self) -> None:
        # -1 encoded as major type 1 with value 0
        self.assertEqual(loads(bytes([0x20])), -1)
        # -10 => -1 - 9
        self.assertEqual(loads(bytes([0x29])), -10)

    def test_trailing_garbage_rejected(self) -> None:
        with self.assertRaises(CborDecodeError):
            loads(bytes([0x01, 0x01]))
