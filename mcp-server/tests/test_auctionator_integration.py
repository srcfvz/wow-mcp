import tempfile
import unittest
from pathlib import Path

from wow_mcp_server.integrations.auctionator import get_auctionator_price, get_vendor_price_copper, list_realm_keys


class TestAuctionatorIntegration(unittest.TestCase):
    def test_decode_minimal_realm_db(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            savedvars_dir = Path(td)
            fixture = (
                "AUCTIONATOR_PRICE_DATABASE = {\n"
                "  [\"__dbversion\"] = 8,\n"
                "  [\"Thunderstrike Horde\"] = \"\\161c123\\162a\\104\\161b10\\24\\42a\\109\\24\\42\",\n"
                "}\n"
                "AUCTIONATOR_VENDOR_PRICE_CACHE = { [\"123\"] = 7.2 }\n"
            )
            (savedvars_dir / "Auctionator.lua").write_text(fixture, encoding="utf-8")

            self.assertEqual(list_realm_keys(savedvars_dir), ["Thunderstrike Horde"])

            price = get_auctionator_price(savedvars_dir, realm_key="Thunderstrike Horde", db_key="123")
            self.assertIsNotNone(price)
            assert price is not None
            self.assertEqual(price.price_copper, 42)

            self.assertEqual(get_vendor_price_copper(savedvars_dir, 123), 7.2)
