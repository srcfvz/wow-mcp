# WowMCP Addon Notes
_Last updated (UTC): 2026-02-11 17:09:11Z._

## Scope
- `WowMCP_State` exports player state snapshots and receives safe command envelopes.
- `WowMCP_Cmd` remains a SavedVariables-only command inbox.

## Slash Command UX (`/wowmcp`)
- `help`, `h`, `?`: show command help and current auto-reload state.
- `chat [show|hide|toggle]`: control the in-game chat panel.
- `ask <text>`: queue one prompt for external processing.
- `autoreload <on|off>`: toggle reload after sending chat messages.
- `status`: show snapshot timestamp, queue sizes, and last command status.
- `snapshot` / `snap`: write a snapshot immediately.
- `cmd` / `lastcmd`: print latest processed command metadata.
- `reload`: manual UI reload (blocked during combat).

## Safety Policy
- Only non-protected command types are processed (`NOTICE`, `CHAT_RESPONSE`, `CHAT_ERROR`, `WAYPOINT`).
- Protected/automation-like command types are blocked and recorded as `blocked_protected`.
- The addon never casts, buys/sells, posts auctions, auto-accepts quests, or performs protected automation.

## Quality Notes
- Chat history/outbox are trimmed to bounded sizes to avoid unbounded SavedVariables growth.
- Chat text is sanitized (control chars removed, whitespace normalized, max length capped).
- UI reload calls are combat-aware and fail safe by queueing until manual reload.
