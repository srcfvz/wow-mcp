import asyncio
import unittest

from wow_mcp_server.crafting import suggest_profitable_crafts


class TestCraftingSuggestions(unittest.TestCase):
    def test_vendor_mats_do_not_limit_crafts(self) -> None:
        crafts_raw = {
            "c:9060534": {
                "name": "Catseye Elixir",
                "profession": "Alchemy",
                "itemString": "i:10592",
                "numResult": 1,
                "mats": {
                    "i:3818": 1,  # Fadeleaf
                    "i:3821": 1,  # Goldthorn
                    "i:3372": 1,  # Leaded Vial (vendor)
                },
                "players": {"Srcfvz": True},
                "hasCD": False,
            }
        }

        have_by_id = {
            3818: 1,
            3821: 1,
            # Intentionally missing 3372 (vendor-bought vial)
        }

        async def get_price(item_id: int) -> dict | None:
            prices = {
                10592: {"source": "auctionator", "unit_price_copper": 5800},  # output
                3818: {"source": "auctionator", "unit_price_copper": 362},
                3821: {"source": "auctionator", "unit_price_copper": 633},
                # Auctionator market price exists for vendor items too; should NOT make it limiting.
                3372: {"source": "auctionator", "unit_price_copper": 644},
            }
            return prices.get(item_id)

        def get_vendor_price(item_id: int) -> float | None:
            return 36.0 if item_id == 3372 else None

        suggestions = asyncio.run(
            suggest_profitable_crafts(
                crafts_raw,
                have_by_id=have_by_id,
                get_price=get_price,
                get_vendor_price=get_vendor_price,
                ah_cut_rate=0.05,
                limit=10,
            )
        )

        self.assertEqual(len(suggestions), 1)
        s = suggestions[0]
        self.assertEqual(s["name"], "Catseye Elixir")
        self.assertEqual(s["max_crafts"], 1)
        self.assertGreater(s["profit_per_craft_copper"], 0)

        vial = [m for m in s["mats"] if m["item_id"] == 3372][0]
        self.assertEqual(vial["price_source"], "vendor")
        self.assertEqual(vial["unit_price_copper"], 36.0)

