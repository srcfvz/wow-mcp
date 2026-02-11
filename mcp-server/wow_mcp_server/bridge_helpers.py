from __future__ import annotations

from typing import Any


def normalize_provider(provider: str | None) -> str:
    p = (provider or "").strip().lower()
    if p in {"openai", "oai"} or "openai" in p:
        return "openai"
    if p in {"anthropic", "claude"} or "anthropic" in p or "claude" in p:
        return "anthropic"
    if p in {"gemini", "google", "google_gemini", "google gemini"} or "gemini" in p:
        return "gemini"
    if p in {"local", "ollama"} or "ollama" in p or "local" in p:
        return "ollama"
    return p or "openai"


def summarize_state_for_prompt(state: dict[str, Any], perms: dict[str, Any]) -> str:
    lines: list[str] = []
    character = state.get("character") if isinstance(state, dict) else None
    if isinstance(character, dict):
        name = character.get("name")
        lvl = character.get("level")
        klass = character.get("class")
        race = character.get("race")
        realm = character.get("realm")
        lines.append(f"Character: {name} (lvl {lvl} {race} {klass}) on {realm}.")

    location = state.get("location") if isinstance(state, dict) else None
    if isinstance(location, dict):
        zone = location.get("zone")
        subzone = location.get("subzone")
        lines.append(f"Location: {zone} / {subzone}.")

    money = state.get("money")
    if isinstance(money, (int, float)):
        lines.append(f"Money (copper): {int(money)}.")

    if perms.get("quests") and isinstance(state.get("quests"), list):
        qs = []
        for q in state["quests"][:10]:
            if isinstance(q, dict) and q.get("title"):
                qs.append(f"{q.get('title')} (lvl {q.get('level')})")
        if qs:
            lines.append("Quests: " + "; ".join(qs) + ".")

    if perms.get("inventory") and isinstance(state.get("bags"), list):
        free = 0
        size = 0
        for b in state["bags"]:
            if isinstance(b, dict):
                size += int(b.get("size") or 0)
                free += int(b.get("free") or 0) if b.get("free") is not None else 0
        if size:
            lines.append(f"Bags: {free}/{size} free slots (approx).")

    return "\n".join(lines).strip()

