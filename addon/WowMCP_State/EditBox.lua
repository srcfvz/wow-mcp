-- EditBox.lua
-- Hidden UI element that listens for clipboard pastes.
-- Logic: If the pasted string starts with "WMCP1:", decode JSON and execute safe actions.

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
local function decode_b64(data)
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

-- Minimal JSON parser for the specific WMCP1 envelope
-- Format expected: {"v":1,"type":"...","payload":"..."}
local function parse_json(s)
    local res = {}
    res.v = tonumber(s:match('"v"%s*:%s*(%d+)'))
    res.type = s:match('"type"%s*:%s*"(.-)"')
    res.payload = s:match('"payload"%s*:%s*"(.-)"')
    -- Unescape simple newlines/quotes if any (llm output might have them)
    if res.payload then
        res.payload = res.payload:gsub("\\n", "\n"):gsub("\\\"", "\"")
    end
    return res
end

-- Function to handle the payload
local function HandlePayload(text)
    if not text or text == "" then return end
    
    if string.find(text, "^WMCP1:") then
        local b64 = string.sub(text, 7)
        local status, decoded = pcall(decode_b64, b64)
        
        if status and decoded then
            local data = parse_json(decoded)
            if not data or not data.type or not data.payload then
                print("|cFFFF0000WowMCP:|r Malformed JSON payload.")
                return
            end

            if data.type == "NOTICE" then
                print("|cFF00FF00WowMCP:|r " .. data.payload)
                frame:Hide()
            elseif data.type == "CHAT_RESPONSE" then
                print("|cFF00FF00WowMCP:|r " .. data.payload)
                -- We don't automatically send it to chat for safety, just print it.
                -- User can copy it if they want or we could put it in the editbox to send.
                frame:Hide()
            elseif data.type == "WAYPOINT" then
                -- Check if TomTom is available
                if SlashCmdList["TOMTOM_WAY"] then
                    print("|cFF00FF00WowMCP:|r Setting Waypoint: " .. data.payload)
                    SlashCmdList["TOMTOM_WAY"](data.payload)
                else
                    print("|cFFFF0000WowMCP:|r TomTom not found. Waypoint: " .. data.payload)
                end
                frame:Hide()
            else
                print("|cFFFF0000WowMCP:|r Blocked unknown command type: " .. data.type)
            end
        else
            print("|cFFFF0000WowMCP:|r Error decoding Base64 payload.")
        end
    elseif string.find(text, "^WMCP:") then
        print("|cFFFF0000WowMCP:|r Legacy WMCP: protocol is deprecated. Please update your bridge.")
    else
        if string.len(text) > 5 then
             -- print("|cFFFFFF00WowMCP:|r Not a valid WowMCP payload.")
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
