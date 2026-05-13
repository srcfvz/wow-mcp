-- ChatLogExporter.lua
-- Forces specific messages to the chat log for the Python tailer.

local function OnChatEvent(self, event, msg, sender, ...)
    -- Filter out system/internal messages from logs if needed.
end

-- Slash command to trigger a test log
SLASH_WOWMCPTEST1 = "/wmcphello"
SlashCmdList["WOWMCPTEST"] = function(msg)
    -- We print to the DEFAULT_CHAT_FRAME, which WoWChatLog.txt tails.
    print("|cFF00FF00WowMCP:|r Hello")
end

-- Slash command to help users remember
SLASH_WOWMCPHELP1 = "/wmcphelp"
SlashCmdList["WOWMCPHELP"] = function(msg)
    print("|cFFFFFF00WowMCP Commands:|r")
    print("  /wmcphello - Trigger a test log for the Python bridge.")
    print("  /wmcpbox   - Toggle the paste-in EditBox.")
end
