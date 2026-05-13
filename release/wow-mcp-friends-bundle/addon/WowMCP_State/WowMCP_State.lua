local addonName = ...

local STATE_VERSION = 1
local ADDON_VERSION = "0.2.0"
local THROTTLE_SECONDS = 1.0
local CHAT_HISTORY_MAX_LINES = 200
local CHAT_OUTBOX_MAX_LINES = 50
local CHAT_TEXT_MAX_CHARS = 500

local function now_utc_iso_z()
  -- UTC timestamp, second precision
  return date("!%Y-%m-%dT%H:%M:%SZ")
end

local function chat(msg)
  if DEFAULT_CHAT_FRAME and DEFAULT_CHAT_FRAME.AddMessage then
    DEFAULT_CHAT_FRAME:AddMessage("|cFF33FF99WowMCP|r: " .. tostring(msg))
  else
    print("WowMCP: " .. tostring(msg))
  end
end

local chatPanel = nil
local chatPanelMessages = nil
local chatPanelInput = nil
local chatPanelAutoReload = nil
local show_notice = nil
local chat_ui_refresh = nil
local ensure_chat_ui = nil
local queue_chat_message = nil

local function safe_tostring(v)
  if v == nil then
    return nil
  end
  return tostring(v)
end

local function trim_tail(list, max_items)
  if type(list) ~= "table" then
    return {}
  end
  if type(max_items) ~= "number" or max_items < 1 then
    return list
  end

  local count = #list
  if count <= max_items then
    return list
  end

  local start = count - max_items + 1
  local out = {}
  for i = start, count do
    out[#out + 1] = list[i]
  end
  return out
end

local function clean_text(text)
  local out = tostring(text or "")
  out = out:gsub("[%z\1-\8\11\12\14-\31]", " ")
  out = out:gsub("%s+", " ")
  out = out:gsub("^%s+", ""):gsub("%s+$", "")
  if #out > CHAT_TEXT_MAX_CHARS then
    out = out:sub(1, CHAT_TEXT_MAX_CHARS)
    out = out:gsub("%s+$", "")
  end
  return out
end

local function register_escape_frame(name)
  if type(UISpecialFrames) ~= "table" or not name then
    return
  end
  for _, existing in ipairs(UISpecialFrames) do
    if existing == name then
      return
    end
  end
  UISpecialFrames[#UISpecialFrames + 1] = name
end

local function in_combat()
  return type(InCombatLockdown) == "function" and InCombatLockdown() and true or false
end

local function request_reload(origin)
  if in_combat() then
    local where = origin and (" (" .. tostring(origin) .. ")") or ""
    chat("Cannot reload in combat" .. where .. ". Request queued.")
    if show_notice then
      show_notice("Queued. Leave combat, then use /wowmcp reload.")
    end
    return false
  end
  ReloadUI()
  return true
end

local function init_state()
  if type(WowMCP_State) ~= "table" then
    WowMCP_State = {}
  end
  WowMCP_State.version = STATE_VERSION
  WowMCP_State.addon = addonName
  WowMCP_State.addon_version = ADDON_VERSION
end

local function ensure_chat_state()
  init_state()
  if type(WowMCP_State.chat) ~= "table" then
    WowMCP_State.chat = {}
  end
  if type(WowMCP_State.chat.history) ~= "table" then
    WowMCP_State.chat.history = {}
  end
  if type(WowMCP_State.chat.outbox) ~= "table" then
    WowMCP_State.chat.outbox = {}
  end
  if type(WowMCP_State.chat.seq) ~= "number" then
    WowMCP_State.chat.seq = 0
  end
  if type(WowMCP_State.chat.auto_reload) ~= "boolean" then
    WowMCP_State.chat.auto_reload = true
  end
end

local function chat_history_add(role, text, seq)
  ensure_chat_state()
  WowMCP_State.chat.history[#WowMCP_State.chat.history + 1] = {
    role = safe_tostring(role),
    text = safe_tostring(clean_text(text)),
    at = now_utc_iso_z(),
    seq = tonumber(seq),
  }

  WowMCP_State.chat.history = trim_tail(WowMCP_State.chat.history, CHAT_HISTORY_MAX_LINES)
end

local function chat_outbox_add(text)
  local cleaned = clean_text(text)
  if cleaned == "" then
    return nil
  end

  ensure_chat_state()
  WowMCP_State.chat.seq = (tonumber(WowMCP_State.chat.seq) or 0) + 1
  local seq = WowMCP_State.chat.seq
  WowMCP_State.chat.outbox[#WowMCP_State.chat.outbox + 1] = {
    seq = seq,
    text = safe_tostring(cleaned),
    at = now_utc_iso_z(),
  }
  WowMCP_State.chat.outbox = trim_tail(WowMCP_State.chat.outbox, CHAT_OUTBOX_MAX_LINES)
  chat_history_add("user", cleaned, seq)
  return seq
end

queue_chat_message = function(text, origin)
  local seq = chat_outbox_add(text)
  if not seq then
    chat("Usage: /wowmcp ask <text>")
    return false
  end

  ensure_chat_ui()
  chatPanel:Show()
  chat_ui_refresh()

  if WowMCP_State.chat and WowMCP_State.chat.auto_reload then
    request_reload(origin or "chat")
  else
    chat("Queued. Use /wowmcp reload to flush SavedVariables.")
    show_notice("Queued. Use /wowmcp reload to flush.")
  end
  return true
end

chat_ui_refresh = function()
  if not chatPanel or not chatPanelMessages then
    return
  end

  ensure_chat_state()

  chatPanelMessages:Clear()
  for _, msg in ipairs(WowMCP_State.chat.history) do
    local role = msg.role or "?"
    local text = msg.text or ""
    if role == "user" then
      chatPanelMessages:AddMessage("|cFFAAAAFFYou|r: " .. tostring(text))
    elseif role == "assistant" then
      chatPanelMessages:AddMessage("|cFFFFFF66AI|r: " .. tostring(text))
    else
      chatPanelMessages:AddMessage("|cFFCCCCCC" .. tostring(role) .. "|r: " .. tostring(text))
    end
  end

  if chatPanelAutoReload and WowMCP_State.chat and type(WowMCP_State.chat.auto_reload) == "boolean" then
    if WowMCP_State.chat.auto_reload then
      chatPanelAutoReload:SetChecked(true)
    else
      chatPanelAutoReload:SetChecked(false)
    end
  end

  if chatPanelMessages and chatPanelMessages.ScrollToBottom then
    chatPanelMessages:ScrollToBottom()
  end
end

ensure_chat_ui = function()
  if chatPanel then
    return
  end

  ensure_chat_state()

  chatPanel = CreateFrame("Frame", "WowMCP_ChatPanel", UIParent, "BasicFrameTemplateWithInset")
  chatPanel:SetSize(480, 360)
  chatPanel:SetPoint("CENTER")
  chatPanel:SetMovable(true)
  chatPanel:EnableMouse(true)
  chatPanel:RegisterForDrag("LeftButton")
  chatPanel:SetScript("OnDragStart", chatPanel.StartMoving)
  chatPanel:SetScript("OnDragStop", chatPanel.StopMovingOrSizing)
  chatPanel:Hide()
  register_escape_frame("WowMCP_ChatPanel")

  chatPanel.title = chatPanel:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
  chatPanel.title:SetPoint("LEFT", chatPanel.TitleBg, "LEFT", 8, 0)
  chatPanel.title:SetText("WowMCP Chat (reload-based)")

  chatPanelMessages = CreateFrame("ScrollingMessageFrame", nil, chatPanel)
  chatPanelMessages:SetPoint("TOPLEFT", 12, -32)
  chatPanelMessages:SetPoint("BOTTOMRIGHT", -12, 70)
  chatPanelMessages:SetFontObject(ChatFontNormal)
  chatPanelMessages:SetJustifyH("LEFT")
  chatPanelMessages:SetFading(false)
  chatPanelMessages:SetMaxLines(250)
  chatPanelMessages:EnableMouseWheel(true)
  chatPanelMessages:SetScript("OnMouseWheel", function(self, delta)
    if delta > 0 then
      self:ScrollUp()
    else
      self:ScrollDown()
    end
  end)

  chatPanelInput = CreateFrame("EditBox", nil, chatPanel, "InputBoxTemplate")
  chatPanelInput:SetPoint("BOTTOMLEFT", 12, 36)
  chatPanelInput:SetSize(320, 22)
  chatPanelInput:SetAutoFocus(false)

  local sendBtn = CreateFrame("Button", nil, chatPanel, "GameMenuButtonTemplate")
  sendBtn:SetPoint("BOTTOMRIGHT", -12, 34)
  sendBtn:SetSize(120, 24)
  sendBtn:SetText("Send (Reload)")
  sendBtn:SetScript("OnClick", function()
    local text = chatPanelInput:GetText() or ""
    chatPanelInput:SetText("")
    queue_chat_message(text, "chat panel send")
  end)

  chatPanelInput:SetScript("OnEnterPressed", function()
    sendBtn:Click()
  end)

  chatPanelAutoReload = CreateFrame("CheckButton", "WowMCP_ChatAutoReload", chatPanel, "UICheckButtonTemplate")
  chatPanelAutoReload:SetPoint("BOTTOMLEFT", 12, 12)
  do
    local label = _G[chatPanelAutoReload:GetName() .. "Text"] or chatPanelAutoReload.text or chatPanelAutoReload.Text
    if label and label.SetText then
      label:SetText("Auto-reload on send")
    end
  end
  chatPanelAutoReload:SetScript("OnClick", function(self)
    ensure_chat_state()
    WowMCP_State.chat.auto_reload = self:GetChecked() and true or false
  end)

  local hint = chatPanel:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
  hint:SetPoint("BOTTOMLEFT", chatPanelAutoReload, "BOTTOMRIGHT", 12, 2)
  hint:SetText("SavedVariables flush on /reload or logout.")

  chat_ui_refresh()
end

local function get_character()
  local name = UnitName("player")
  local realm = GetRealmName and GetRealmName() or nil
  local level = UnitLevel("player")
  local _, class = UnitClass("player")
  local _, race = UnitRace("player")
  local faction = UnitFactionGroup("player")
  return {
    name = safe_tostring(name),
    realm = safe_tostring(realm),
    level = tonumber(level) or 0,
    class = safe_tostring(class),
    race = safe_tostring(race),
    faction = safe_tostring(faction),
  }
end

local function get_location()
  local zone = GetZoneText and GetZoneText() or nil
  local subzone = GetSubZoneText and GetSubZoneText() or nil

  local mapID = nil
  local x = nil
  local y = nil
  if C_Map and C_Map.GetBestMapForUnit and C_Map.GetPlayerMapPosition then
    mapID = C_Map.GetBestMapForUnit("player")
    if mapID then
      local pos = C_Map.GetPlayerMapPosition(mapID, "player")
      if pos and pos.GetXY then
        x, y = pos:GetXY()
      end
    end
  end

  local out = { zone = safe_tostring(zone), subzone = safe_tostring(subzone) }
  if mapID then
    out.map_id = mapID
  end
  if x and y then
    out.x = x
    out.y = y
  end
  return out
end

local function get_bags_summary()
  local bags = {}

  local getNumSlots = C_Container and C_Container.GetContainerNumSlots or GetContainerNumSlots
  local getNumFreeSlots = C_Container and C_Container.GetContainerNumFreeSlots or GetContainerNumFreeSlots

  if type(getNumSlots) ~= "function" then
    return bags
  end

  for bag = 0, 4 do
    local size = getNumSlots(bag)
    local free = nil
    if type(getNumFreeSlots) == "function" then
      free = select(1, getNumFreeSlots(bag))
    end
    bags[#bags + 1] = {
      bag = bag,
      size = tonumber(size) or 0,
      free = tonumber(free),
    }
  end

  return bags
end

local function get_quests()
  local quests = {}

  if C_QuestLog and C_QuestLog.GetNumQuestLogEntries and C_QuestLog.GetInfo then
    local n = C_QuestLog.GetNumQuestLogEntries()
    for i = 1, n do
      local info = C_QuestLog.GetInfo(i)
      if info and not info.isHeader then
        quests[#quests + 1] = {
          title = safe_tostring(info.title),
          level = tonumber(info.level),
          quest_id = tonumber(info.questID),
          is_complete = info.isComplete,
          frequency = tonumber(info.frequency),
        }
      end
    end
    return quests
  end

  if type(GetNumQuestLogEntries) == "function" and type(GetQuestLogTitle) == "function" then
    local n = GetNumQuestLogEntries()
    for i = 1, n do
      local title, level, _, isHeader, _, isComplete, frequency, questID = GetQuestLogTitle(i)
      if title and not isHeader then
        quests[#quests + 1] = {
          title = safe_tostring(title),
          level = tonumber(level),
          quest_id = tonumber(questID),
          is_complete = isComplete,
          frequency = tonumber(frequency),
        }
      end
    end
  end

  return quests
end

local function get_talents()
  if type(GetNumTalentTabs) ~= "function" or type(GetTalentTabInfo) ~= "function" then
    return nil
  end

  local tabs = {}
  local best_index = nil
  local best_points = -1
  local total_points = 0

  local num_tabs = GetNumTalentTabs() or 0
  for tab = 1, num_tabs do
    local name, icon_texture, points_spent, file_name = GetTalentTabInfo(tab)
    points_spent = tonumber(points_spent) or 0
    total_points = total_points + points_spent

    if points_spent > best_points then
      best_points = points_spent
      best_index = tab
    end

    local talents = {}
    if type(GetNumTalents) == "function" and type(GetTalentInfo) == "function" then
      local n = GetNumTalents(tab) or 0
      for i = 1, n do
        local t_name, _, tier, column, rank, max_rank = GetTalentInfo(tab, i)
        if t_name then
          talents[#talents + 1] = {
            name = safe_tostring(t_name),
            tier = tonumber(tier),
            column = tonumber(column),
            rank = tonumber(rank) or 0,
            max_rank = tonumber(max_rank) or 0,
          }
        end
      end
    end

    tabs[#tabs + 1] = {
      index = tab,
      name = safe_tostring(name),
      file_name = safe_tostring(file_name),
      icon = safe_tostring(icon_texture),
      points_spent = points_spent,
      talents = talents,
    }
  end

  local spec = nil
  if best_index ~= nil and best_index >= 1 and best_index <= #tabs then
    spec = {
      primary_tab = best_index,
      primary_tab_name = tabs[best_index].name,
      points = { tabs[1] and tabs[1].points_spent or 0, tabs[2] and tabs[2].points_spent or 0, tabs[3] and tabs[3].points_spent or 0 },
      total_points = total_points,
    }
  end

  return {
    total_points = total_points,
    spec = spec,
    tabs = tabs,
  }
end

local function get_skills()
  if type(GetNumSkillLines) ~= "function" or type(GetSkillLineInfo) ~= "function" then
    return nil
  end

  local skills = {}
  local n = GetNumSkillLines() or 0
  for i = 1, n do
    local name, is_header, is_expanded, rank, num_temp_points, modifier, max_rank, is_abandonable = GetSkillLineInfo(i)
    if name then
      skills[#skills + 1] = {
        name = safe_tostring(name),
        is_header = is_header and true or false,
        is_expanded = is_expanded and true or false,
        rank = tonumber(rank),
        max_rank = tonumber(max_rank),
        modifier = tonumber(modifier),
        temp_points = tonumber(num_temp_points),
        is_abandonable = is_abandonable and true or false,
      }
    end
  end

  return skills
end

local noticeFrame = nil

show_notice = function(text)
  if noticeFrame == nil then
    noticeFrame = CreateFrame("Frame", "WowMCP_NoticeFrame", UIParent)
    noticeFrame:SetSize(420, 120)
    noticeFrame:SetPoint("CENTER", UIParent, "CENTER", 0, 180)
    noticeFrame:SetFrameStrata("DIALOG")
    noticeFrame:EnableMouse(true)
    noticeFrame:SetMovable(true)
    noticeFrame:RegisterForDrag("LeftButton")
    noticeFrame:SetScript("OnDragStart", function(self)
      self:StartMoving()
    end)
    noticeFrame:SetScript("OnDragStop", function(self)
      self:StopMovingOrSizing()
    end)

    local bg = noticeFrame:CreateTexture(nil, "BACKGROUND")
    bg:SetAllPoints(true)
    bg:SetColorTexture(0, 0, 0, 0.75)

    local border = CreateFrame("Frame", nil, noticeFrame)
    border:SetAllPoints(true)
    local b = border:CreateTexture(nil, "BORDER")
    b:SetAllPoints(true)
    b:SetColorTexture(1, 1, 1, 0.08)

    local title = noticeFrame:CreateFontString(nil, "ARTWORK", "GameFontNormalLarge")
    title:SetPoint("TOPLEFT", noticeFrame, "TOPLEFT", 12, -10)
    title:SetText("WowMCP")

    local close = CreateFrame("Button", nil, noticeFrame, "UIPanelCloseButton")
    close:SetPoint("TOPRIGHT", noticeFrame, "TOPRIGHT", -2, -2)

    local fs = noticeFrame:CreateFontString(nil, "ARTWORK", "GameFontHighlight")
    fs:SetPoint("TOPLEFT", title, "BOTTOMLEFT", 0, -10)
    fs:SetPoint("BOTTOMRIGHT", noticeFrame, "BOTTOMRIGHT", -12, 12)
    fs:SetJustifyH("LEFT")
    fs:SetJustifyV("TOP")
    fs:SetText("")
    noticeFrame.text = fs

    noticeFrame:Hide()
    register_escape_frame("WowMCP_NoticeFrame")
  end

  noticeFrame.text:SetText(tostring(text or ""))
  noticeFrame:Show()
end

local BLOCKED_CMD_TYPES = {
  ACCEPT_QUEST = true,
  AUTO_BUY = true,
  AUTO_SELL = true,
  BUY = true,
  CAST = true,
  INTERACT = true,
  POST_AUCTION = true,
  TARGET = true,
  TURN_IN = true,
  USE_ITEM = true,
}

local function handle_waypoint(payload)
  if type(payload) ~= "table" then
    return
  end

  local mapID = tonumber(payload.map_id or payload.mapID)
  local x = tonumber(payload.x)
  local y = tonumber(payload.y)
  local title = payload.title or payload.name or "WowMCP"

  if not (mapID and x and y) then
    chat("WAYPOINT: missing map_id/x/y")
    return
  end

  if TomTom and TomTom.AddWaypoint then
    TomTom:AddWaypoint(mapID, x, y, { title = tostring(title), persistent = false, minimap = true, world = true })
    chat(("WAYPOINT set: %s (map %d, %.1f, %.1f)"):format(tostring(title), mapID, x * 100, y * 100))
    return
  end

  chat("WAYPOINT: TomTom not available (install/enable TomTom).")
end

local function handle_cmd()
  if type(WowMCP_Cmd) ~= "table" then
    return
  end

  local id = safe_tostring(WowMCP_Cmd.id)
  local cmdTypeRaw = safe_tostring(WowMCP_Cmd.type)
  local payload = WowMCP_Cmd.payload

  if id then
    id = id:gsub("^%s+", ""):gsub("%s+$", "")
  end

  local cmdType = nil
  if cmdTypeRaw then
    cmdType = string.upper(cmdTypeRaw)
  end

  if not id or id == "" or not cmdType or cmdType == "" then
    return
  end

  if WowMCP_State and WowMCP_State.last_cmd_id == id then
    return
  end

  if WowMCP_State then
    WowMCP_State.last_cmd_id = id
    WowMCP_State.last_cmd_type = cmdType
    WowMCP_State.last_cmd_at = now_utc_iso_z()
    WowMCP_State.last_cmd_status = "received"
  end

  if BLOCKED_CMD_TYPES[cmdType] then
    chat(("Blocked command type %s: protected automation is not allowed."):format(cmdType))
    show_notice(("Blocked %s command (safety policy)."):format(cmdType))
    if WowMCP_State then
      WowMCP_State.last_cmd_status = "blocked_protected"
    end
    return
  end

  if cmdType == "NOTICE" then
    local msg = nil
    if type(payload) == "table" then
      msg = payload.message or payload.text
    end
    msg = clean_text(msg or ("NOTICE (" .. id .. ")"))
    chat(msg)
    show_notice(msg)
    if WowMCP_State then
      WowMCP_State.last_cmd_status = "processed_notice"
    end
    return
  end

  if cmdType == "CHAT_RESPONSE" then
    local msg = nil
    if type(payload) == "table" then
      msg = payload.text or payload.message
    end
    msg = clean_text(msg or "(empty response)")

    ensure_chat_state()
    chat_history_add("assistant", msg, tonumber(payload and payload.seq))
    ensure_chat_ui()
    chatPanel:Show()
    chat_ui_refresh()
    show_notice("AI reply received. Open /wowmcp chat")
    if WowMCP_State then
      WowMCP_State.last_cmd_status = "processed_chat_response"
    end
    return
  end

  if cmdType == "CHAT_ERROR" then
    local msg = nil
    if type(payload) == "table" then
      msg = payload.error or payload.message or payload.text
    end
    msg = clean_text(msg or "(unknown error)")
    ensure_chat_state()
    chat_history_add("system", "ERROR: " .. tostring(msg), nil)
    ensure_chat_ui()
    chatPanel:Show()
    chat_ui_refresh()
    show_notice("AI error. Open /wowmcp chat")
    if WowMCP_State then
      WowMCP_State.last_cmd_status = "processed_chat_error"
    end
    return
  end

  if cmdType == "WAYPOINT" then
    handle_waypoint(payload)
    if WowMCP_State then
      WowMCP_State.last_cmd_status = "processed_waypoint"
    end
    return
  end

  chat(("Ignoring unsupported cmd %s (%s). Use NOTICE/CHAT_RESPONSE/CHAT_ERROR/WAYPOINT."):format(cmdType, id))
  if WowMCP_State then
    WowMCP_State.last_cmd_status = "ignored_unsupported"
  end
end

local pending = false
local pending_reason = {}

local function write_snapshot()
  init_state()
  ensure_chat_state()
  WowMCP_State.generated_at = now_utc_iso_z()
  WowMCP_State.generated_unix = tonumber(time and time() or 0)
  WowMCP_State.character = get_character()
  WowMCP_State.money = GetMoney and GetMoney() or 0
  WowMCP_State.location = get_location()
  WowMCP_State.in_combat = in_combat()
  WowMCP_State.bags = get_bags_summary()
  WowMCP_State.quests = get_quests()
  WowMCP_State.talents = get_talents()
  WowMCP_State.skills = get_skills()
  WowMCP_State.chat_outbox_size = #WowMCP_State.chat.outbox

  local reasons = {}
  for k in pairs(pending_reason) do
    reasons[#reasons + 1] = k
  end
  table.sort(reasons)
  WowMCP_State.last_update_reasons = reasons
  pending_reason = {}
end

local function schedule_snapshot(reason)
  if reason then
    pending_reason[tostring(reason)] = true
  end
  if pending then
    return
  end
  pending = true

  if C_Timer and C_Timer.After then
    C_Timer.After(THROTTLE_SECONDS, function()
      pending = false
      write_snapshot()
    end)
  else
    pending = false
    write_snapshot()
  end
end

local frame = CreateFrame("Frame")
frame:RegisterEvent("PLAYER_LOGIN")
frame:RegisterEvent("PLAYER_ENTERING_WORLD")
frame:RegisterEvent("PLAYER_LEVEL_UP")
frame:RegisterEvent("CHARACTER_POINTS_CHANGED")
frame:RegisterEvent("PLAYER_MONEY")
frame:RegisterEvent("BAG_UPDATE_DELAYED")
frame:RegisterEvent("QUEST_LOG_UPDATE")
frame:RegisterEvent("SKILL_LINES_CHANGED")
frame:RegisterEvent("ZONE_CHANGED")
frame:RegisterEvent("ZONE_CHANGED_INDOORS")
frame:RegisterEvent("ZONE_CHANGED_NEW_AREA")
frame:RegisterEvent("PLAYER_LOGOUT")

frame:SetScript("OnEvent", function(_, event)
  if event == "PLAYER_LOGOUT" then
    -- Ensure the latest snapshot is present in SavedVariables written on /reload or logout.
    write_snapshot()
    return
  end

  if event == "PLAYER_LOGIN" then
    init_state()
    handle_cmd()
    ensure_chat_state()
    schedule_snapshot(event)
    chat(("loaded v%s. Use /wowmcp help for commands."):format(ADDON_VERSION))
    return
  end

  if event == "PLAYER_ENTERING_WORLD" then
    handle_cmd()
  end

  schedule_snapshot(event)
end)

local function print_help()
  ensure_chat_state()
  local auto_reload = WowMCP_State.chat and WowMCP_State.chat.auto_reload and "ON" or "OFF"
  chat("Commands:")
  chat("  /wowmcp help - Show this help.")
  chat("  /wowmcp chat [show|hide|toggle] - Open the in-game chat panel.")
  chat("  /wowmcp ask <text> - Queue a chat prompt for bridge processing.")
  chat("  /wowmcp autoreload <on|off> - Toggle auto /reload on send.")
  chat("  /wowmcp status - Show snapshot + queue status.")
  chat("  /wowmcp snapshot - Write a fresh state snapshot now.")
  chat("  /wowmcp cmd - Show last processed command envelope.")
  chat("  /wowmcp reload - Reload UI (blocked while in combat).")
  chat(("Auto-reload is currently %s."):format(auto_reload))
  chat("Safety: protected actions are never automated.")
end

local function set_auto_reload(enabled)
  ensure_chat_state()
  WowMCP_State.chat.auto_reload = enabled and true or false
  if chatPanelAutoReload then
    chatPanelAutoReload:SetChecked(WowMCP_State.chat.auto_reload)
  end
end

local function show_status()
  ensure_chat_state()

  local generated_at = WowMCP_State.generated_at or "n/a"
  local queue_size = #WowMCP_State.chat.outbox
  local history_size = #WowMCP_State.chat.history
  local auto_reload = WowMCP_State.chat.auto_reload and "ON" or "OFF"
  chat(("Status: snapshot=%s, outbox=%d, history=%d, auto-reload=%s"):format(generated_at, queue_size, history_size, auto_reload))

  if WowMCP_State.last_cmd_id then
    local status = WowMCP_State.last_cmd_status or "unknown"
    local at = WowMCP_State.last_cmd_at or "n/a"
    chat(("Last cmd: %s (%s) at %s [%s]"):format(
      tostring(WowMCP_State.last_cmd_type),
      tostring(WowMCP_State.last_cmd_id),
      tostring(at),
      tostring(status)
    ))
  else
    chat("Last cmd: none")
  end
end

SLASH_WOWMCP1 = "/wowmcp"
SlashCmdList["WOWMCP"] = function(msg)
  msg = clean_text(msg or "")

  if msg == "" then
    print_help()
    return
  end

  local raw_command, raw_args = msg:match("^(%S+)%s*(.*)$")
  local command = raw_command and string.lower(raw_command) or ""
  local args = raw_args or ""

  if command == "help" or command == "h" or command == "?" then
    print_help()
    return
  end

  if command == "chat" then
    local action = string.lower(args)
    if action ~= "" and action ~= "show" and action ~= "hide" and action ~= "toggle" then
      chat("Usage: /wowmcp chat [show|hide|toggle]")
      return
    end

    ensure_chat_ui()
    if action == "show" then
      chatPanel:Show()
      chat_ui_refresh()
      return
    end

    if action == "hide" then
      chatPanel:Hide()
      return
    end

    if chatPanel:IsShown() and action ~= "show" then
      chatPanel:Hide()
    else
      chatPanel:Show()
      chat_ui_refresh()
    end
    return
  end

  if command == "ask" then
    queue_chat_message(args, "slash ask")
    return
  end

  if command == "autoreload" then
    local value = string.lower(args)
    if value == "on" or value == "1" or value == "true" then
      set_auto_reload(true)
      chat("Auto-reload enabled.")
      return
    end
    if value == "off" or value == "0" or value == "false" then
      set_auto_reload(false)
      chat("Auto-reload disabled.")
      return
    end
    chat("Usage: /wowmcp autoreload <on|off>")
    return
  end

  if command == "status" then
    show_status()
    return
  end

  if command == "snapshot" or command == "snap" then
    write_snapshot()
    chat("Snapshot updated (SavedVariables writes on logout or /reload).")
    return
  end

  if command == "cmd" or command == "lastcmd" then
    show_status()
    return
  end

  if command == "reload" then
    request_reload("slash command")
    return
  end

  chat(("Unknown command '%s'. Use /wowmcp help."):format(tostring(command)))
end
