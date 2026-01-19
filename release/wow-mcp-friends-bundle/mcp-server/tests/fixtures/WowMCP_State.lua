-- WoW MCP SavedVariables test fixture

WowMCP_State = {
  version = 1,
  generated_at = "2026-01-14T00:00:00Z",
  character = { name = "Testy", realm = "ExampleRealm", level = 12, class = "MAGE" },
  money = 123456,
  flags = { true, false, nil },
  items = {
    [1] = { id = 6948, name = "Hearthstone" },
    [2] = { id = 117, name = "Tough Jerky" },
  },
  mixed = { "a", "b", [5] = "e", key = "v" },
  note = "line1\\nline2",
}

WowMCP_Cmd = nil
