-- EditBox.lua
-- Hidden UI element that listens for clipboard pastes.
-- Logic: If the pasted string starts with "WMCP:", decode and execute it.

local frame = CreateFrame("Frame", "WowMCP_PasteFrame", UIParent, "BackdropTemplate")
frame:SetSize(400, 100)
frame:SetPoint("CENTER")
frame:SetBackdrop({
    bgFile = "Interface\\ChatFrame\\ChatFrameBackground",
    edgeFile = "Interface\\Buttons\\WHITE8X8",
    edgeSize = 1,
})
frame:SetBackdropColor(0, 0, 0, 0.9)
frame:Hide() -- Hide by default

local title = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
title:SetPoint("TOPLEFT", 10, -10)
title:SetText("WowMCP Paste Box (Paste command here)")

local eb = CreateFrame("EditBox", "WowMCP_PasteBox", frame, "InputBoxTemplate")
eb:SetSize(380, 20)
eb:SetPoint("TOPLEFT", 10, -40)
eb:SetAutoFocus(false)

-- Helper: Simple Base64 Decode
local b='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
local function decode(data)
    data = string.gsub(data, '[^'..b..'=]', '')
    return (data:gsub('.', function(x)
        if (x == '=') then return '' end
        local r,f='',(b:find(x)-1)
        for i=6,1,-1 do r=r..(f%2^i-f%2^(i-1)>0 and '1' or '0') end
        return r;
    end):gsub('%d%d%d%d%d%d%d%d', function(x)
        local r=0
        for i=1,8 do r=r+(x:sub(i,i)=='1' and 2^(8-i) or 0) end
        return string.char(r)
    end))
end

-- Function to handle the payload
local function HandlePayload(text)
    if not text or text == "" then return end
    
    if string.find(text, "^WMCP:") then
        local b64 = string.sub(text, 6)
        local status, decoded = pcall(decode, b64)
        
        if status and decoded then
            if string.find(decoded, "^/") then
                -- It's a slash command (e.g. /way)
                print("|cFF00FF00WowMCP:|r Executing command: " .. decoded)
                ChatFrame_OpenChat(decoded, DEFAULT_CHAT_FRAME)
                ChatEdit_SendText(DEFAULT_CHAT_FRAME.editBox, 0)
            else
                -- It's just a message
                print("|cFF00FF00WowMCP Response:|r " .. decoded)
            end
            
            -- Hide the box after successful paste
            frame:Hide()
        else
            print("|cFFFF0000WowMCP:|r Error decoding Base64 payload.")
        end
    else
        -- If it doesn't have the prefix, maybe the user just pasted something else.
        -- We can just ignore it or show a hint.
        -- For now, let's be quiet unless it looks like a failed attempt at WMCP.
        if string.len(text) > 5 and not string.find(text, "^WMCP:") then
             print("|cFFFFFF00WowMCP:|r Not a valid WowMCP payload (must start with WMCP:)")
        end
    end
end

eb:SetScript("OnTextChanged", function(self, userInput)
    if userInput then
        local text = self:GetText()
        HandlePayload(text)
        self:SetText("") -- Clear for next paste
    end
end)

eb:SetScript("OnEscapePressed", function(self)
    frame:Hide()
end)

-- Toggle command
SLASH_WOWMCPBOX1 = "/wmcpbox"
SlashCmdList["WOWMCPBOX"] = function(msg)
    if frame:IsShown() then
        frame:Hide()
    else
        frame:Show()
        eb:SetFocus()
    end
end
