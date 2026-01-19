import tempfile
import unittest
from pathlib import Path

from wow_mcp_server.integrations.tradeskillmaster import iter_crafts, list_craft_scopes, load_crafts


class TestTradeSkillMasterIntegration(unittest.TestCase):
    def test_list_and_parse_crafts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            savedvars_dir = Path(td)
            fixture = (
                "TradeSkillMasterDB = {\n"
                "  [\"f@Horde - Thunderstrike@internalData@crafts\"] = {\n"
                "    [\"c:1\"] = {\n"
                "      [\"name\"] = \"Test Potion\",\n"
                "      [\"profession\"] = \"Alchemy\",\n"
                "      [\"itemString\"] = \"i:1000\",\n"
                "      [\"numResult\"] = 1,\n"
                "      [\"hasCD\"] = false,\n"
                "      [\"players\"] = { [\"Srcfvz - Thunderstrike\"] = true },\n"
                "      [\"mats\"] = {\n"
                "        [\"i:2000\"] = 2,\n"
                "        [\"i:2001\"] = 1,\n"
                "      },\n"
                "    },\n"
                "  },\n"
                "}\n"
            )
            (savedvars_dir / "TradeSkillMaster.lua").write_text(fixture, encoding="utf-8")

            self.assertEqual(list_craft_scopes(savedvars_dir), ["Horde - Thunderstrike"])

            crafts = load_crafts(savedvars_dir, "Horde - Thunderstrike")
            parsed = list(iter_crafts(crafts))
            self.assertEqual(len(parsed), 1)
            craft = parsed[0]
            self.assertEqual(craft.name, "Test Potion")
            self.assertEqual(craft.profession, "Alchemy")
            self.assertEqual(craft.output_item_id, 1000)
            self.assertEqual(craft.num_result, 1)
            self.assertEqual(craft.mats, {2000: 2, 2001: 1})
            self.assertEqual(craft.players, ["Srcfvz - Thunderstrike"])

