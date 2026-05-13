import os
import json
import base64
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

# --- Shared Utilities ---

def _http_post_json(url: str, headers: dict, payload: dict, timeout_s: float = 45.0) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={**headers, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8", errors="replace"))

def call_llm(prompt: str, context: str, provider: str, model: str, config: dict) -> str:
    """
    Common LLM calling logic for both CLI and GUI bridges.
    """
    system_prompt = (
        "You are a helpful WoW assistant. Keep answers short (max 2 sentences). "
        "Never suggest botting or protected-action automation.\n"
        f"Context:\n{context}"
    )
    
    # Normalize provider
    from wow_mcp_server.bridge_helpers import normalize_provider
    provider = normalize_provider(provider)
    
    # Provider-specific logic
    if provider == "ollama":
        url = os.environ.get("OLLAMA_HOST", "http://localhost:11434") + "/api/chat"
        payload = {
            "model": model or "llama3.1",
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        }
        try:
            data = _http_post_json(url, {}, payload)
            return data.get("message", {}).get("content", "").strip()
        except Exception as e:
            return f"Error calling Ollama: {e}"

    # API Based Providers (OpenAI, GitHub, Groq, OpenRouter, Anthropic)
    api_key = config.get("api_key")
    headers = {"Authorization": f"Bearer {api_key}"}
    url = "https://api.openai.com/v1/chat/completions"

    if provider == "github":
        url = "https://models.github.ai/inference/chat/completions"
        headers = {"Authorization": f"Bearer {config.get('github_token')}"}
    elif provider == "groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {config.get('groq_key')}"}
    elif provider == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.get('openrouter_key')}",
            "HTTP-Referer": "https://github.com/google/gemini-cli",
            "X-Title": "WowMCP"
        }
    elif provider == "anthropic":
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": model or "claude-3-5-sonnet-latest",
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}]
        }
        try:
            data = _http_post_json(url, headers, payload)
            return data.get("content", [{}])[0].get("text", "").strip()
        except Exception as e:
            return f"Error calling Anthropic: {e}"

    # Default to OpenAI-compatible
    if not headers.get("Authorization") or "Bearer " == headers.get("Authorization"):
         return f"Error: API Key for {provider} not set."

    payload = {
        "model": model or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    try:
        data = _http_post_json(url, headers, payload)
        return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        return f"Error calling {provider}: {e}"

def process_log_line(line: str, last_state: dict, config: dict, log_fn: callable) -> Optional[dict]:
    """
    Parses a log line and returns a request if a trigger is detected.
    """
    trigger = None
    if "!ai " in line:
        trigger = "!ai "
    elif "!wmcp " in line:
        trigger = "!wmcp "
    
    if not trigger:
        return None

    # Sender verification
    player_name = last_state.get("character", {}).get("name")
    if player_name and f"[{player_name}]" not in line:
        return None

    parts = line.split(trigger, 1)
    if len(parts) > 1:
        prompt = parts[1].strip()
        log_fn(f"Trigger: {prompt}")
        return {"prompt": prompt, "trigger": trigger}
    
    return None

def extract_msg_type_and_payload(response: str) -> (str, str):
    """
    Heuristically decides message type from LLM response.
    """
    msg_type = "NOTICE"
    payload = response
    
    if "/way " in response:
        # Check if it starts with /way or contains it
        way_parts = response.split("/way ", 1)
        if len(way_parts) > 1:
            msg_type = "WAYPOINT"
            payload = way_parts[1].strip()
            # Clean up trailing text if any
            if " " in payload:
                # TomTom usually takes x y [name]
                pass
    
    return msg_type, payload
