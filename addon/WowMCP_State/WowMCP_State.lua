local addonName = ...

local STATE_VERSION = 1
local ADDON_VERSION = "0.1.0"
local THROTTLE_SECONDS = 1.0

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

local function safe_tostring(v)
  if v == nil then
    return nil
  end
  return tostring(v)
end

local function init_state()
  if type(WowMCP_State) ~= "table" then
    WowMCP_State = {}
  end
  WowMCP_State.version = STATE_VERSION
  WowMCP_State.addon = addonName
  WowMCP_State.addon_version = ADDON_VERSION
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

local function show_notice(text)
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
  end

  noticeFrame.text:SetText(tostring(text or ""))
  noticeFrame:Show()
end

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
  local cmdType = safe_tostring(WowMCP_Cmd.type)
  local payload = WowMCP_Cmd.payload

  if not id or not cmdType then
    return
  end

  if WowMCP_State and WowMCP_State.last_cmd_id == id then
    return
  end

  if WowMCP_State then
    WowMCP_State.last_cmd_id = id
    WowMCP_State.last_cmd_type = cmdType
    WowMCP_State.last_cmd_at = now_utc_iso_z()
  end

  if cmdType == "NOTICE" then
    local msg = nil
    if type(payload) == "table" then
      msg = payload.message or payload.text
    end
    msg = msg or ("NOTICE (" .. id .. ")")
    chat(msg)
    show_notice(msg)
    return
  end

  if cmdType == "WAYPOINT" then
    handle_waypoint(payload)
    return
  end

  chat(("CMD %s (%s) received."):format(cmdType, id))
end

local pending = false
local pending_reason = {}

local function write_snapshot()
  init_state()
  WowMCP_State.generated_at = now_utc_iso_z()
  WowMCP_State.character = get_character()
  WowMCP_State.money = GetMoney and GetMoney() or 0
  WowMCP_State.location = get_location()
  WowMCP_State.bags = get_bags_summary()
  WowMCP_State.quests = get_quests()
  WowMCP_State.talents = get_talents()
  WowMCP_State.skills = get_skills()

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
    schedule_snapshot(event)
    chat("loaded. Use /wowmcp for commands.")
    return
  end

  if event == "PLAYER_ENTERING_WORLD" then
    handle_cmd()
  end

  schedule_snapshot(event)
end)

SLASH_WOWMCP1 = "/wowmcp"
SlashCmdList["WOWMCP"] = function(msg)
  msg = msg or ""
  msg = msg:gsub("^%s+", ""):gsub("%s+$", "")
  local lower = string.lower(msg)

  if lower == "" or lower == "help" then
    chat("Commands: /wowmcp snapshot | /wowmcp cmd | /wowmcp reload")
    return
  end

  if lower == "snapshot" then
    write_snapshot()
    chat("Snapshot updated (SavedVariables writes on logout or /reload).")
    return
  end

  if lower == "cmd" then
    if WowMCP_State and WowMCP_State.last_cmd_id then
      chat(("Last cmd: %s (%s)"):format(tostring(WowMCP_State.last_cmd_type), tostring(WowMCP_State.last_cmd_id)))
    else
      chat("No cmd processed yet.")
    end
    return
  end

  if lower == "reload" then
    ReloadUI()
    return
  end

  chat("Unknown command. Use /wowmcp help")
end
