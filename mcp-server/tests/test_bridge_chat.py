import unittest


class TestBridgeChatHelpers(unittest.TestCase):
    def test_normalize_provider(self):
        from wow_mcp_server.bridge_helpers import normalize_provider

        self.assertEqual(normalize_provider("OpenAI"), "openai")
        self.assertEqual(normalize_provider("Anthropic"), "anthropic")
        self.assertEqual(normalize_provider("Google Gemini"), "gemini")
        self.assertEqual(normalize_provider("Local (Ollama)"), "ollama")

    def test_summarize_state(self):
        from wow_mcp_server.bridge_helpers import summarize_state_for_prompt

        state = {
            "character": {"name": "Test", "level": 12, "class": "MAGE", "race": "HUMAN", "realm": "X"},
            "location": {"zone": "Elwynn Forest", "subzone": "Goldshire"},
            "money": 12345,
            "quests": [{"title": "A", "level": 10}, {"title": "B", "level": 11}],
            "bags": [{"size": 16, "free": 4}, {"size": 8, "free": 2}],
        }
        text = summarize_state_for_prompt(state, {"quests": True, "inventory": True})
        self.assertIn("Character:", text)
        self.assertIn("Location:", text)
        self.assertIn("Quests:", text)
        self.assertIn("Bags:", text)


if __name__ == "__main__":
    unittest.main()
