import tempfile
import unittest
from pathlib import Path

from wow_mcp_server.integrations.tsm_apphelper import TsmAppHelperError, get_price_copper, list_scope_keys


class TestTsmAppHelperIntegration(unittest.TestCase):
    def test_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            savedvars_dir = Path(td)
            with self.assertRaises(TsmAppHelperError):
                list_scope_keys(savedvars_dir)

    def test_simple_dbmarket_table(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            savedvars_dir = Path(td)
            fixture = (
                "TradeSkillMaster_AppHelperDB = {\n"
                "  [\"factionrealm\"] = {\n"
                "    [\"Horde - Thunderstrike\"] = {\n"
                "      [\"prices\"] = {\n"
                "        [\"dbmarket\"] = {\n"
                "          [\"i:123\"] = 456,\n"
                "        },\n"
                "      },\n"
                "    },\n"
                "  },\n"
                "}\n"
            )
            (savedvars_dir / "TradeSkillMaster_AppHelper.lua").write_text(fixture, encoding="utf-8")

            self.assertEqual(list_scope_keys(savedvars_dir), ["Horde - Thunderstrike"])

            price = get_price_copper(savedvars_dir, item_id=123, scope_key="Horde - Thunderstrike")
            self.assertIsNotNone(price)
            assert price is not None
            self.assertEqual(price.unit_price_copper, 456)
            self.assertEqual(price.item_key, "i:123")

            # Fallback scan without specifying scope.
            price2 = get_price_copper(savedvars_dir, item_id=123)
            self.assertIsNotNone(price2)
            assert price2 is not None
            self.assertEqual(price2.unit_price_copper, 456)
            self.assertIsNone(price2.scope_key)

