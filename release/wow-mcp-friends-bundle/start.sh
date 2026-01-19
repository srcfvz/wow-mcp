#!/usr/bin/env bash
set -euo pipefail

err() { printf '%s\n' "$*" >&2; }

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

if [[ -z "${WOW_SAVEDVARS_DIR_HOST:-}" ]]; then
  err "ERROR: WOW_SAVEDVARS_DIR_HOST is not set."
  err
  err "Set it to your WoW account SavedVariables directory, for example:"
  err "  export WOW_SAVEDVARS_DIR_HOST='/path/to/World of Warcraft/.../WTF/Account/<ACCOUNT>/SavedVariables'"
  err
  err "Tip: create a .env file next to start.sh (gitignored) with WOW_SAVEDVARS_DIR_HOST and WOW_SCAN_ROOT_HOST."
  err
  err "Build once:"
  err "  docker compose build wow-mcp"
  exit 2
fi

export WOW_SCAN_ROOT_HOST="${WOW_SCAN_ROOT_HOST:-$WOW_SAVEDVARS_DIR_HOST}"

IMAGE="wow-mcp:local"
if ! docker image inspect "${IMAGE}" >/dev/null 2>&1; then
  err "ERROR: Docker image not built yet."
  err "Run: docker compose build wow-mcp"
  exit 2
fi

exec docker run --rm -i --network none \
  -v "${WOW_SAVEDVARS_DIR_HOST}:/wow/SavedVariables:rw" \
  -v "${WOW_SCAN_ROOT_HOST}:/wow/scan:ro" \
  -e WOW_SAVEDVARS_DIR=/wow/SavedVariables \
  -e WOW_STATE_FILE="${WOW_STATE_FILE:-WowMCP_State.lua}" \
  -e WOW_STATE_VAR="${WOW_STATE_VAR:-WowMCP_State}" \
  -e WOW_CMD_FILE="${WOW_CMD_FILE:-WowMCP_Cmd.lua}" \
  -e WOW_CMD_VAR="${WOW_CMD_VAR:-WowMCP_Cmd}" \
  -e WOW_SCAN_ROOT=/wow/scan \
  -e WOW_PROBE_MAX_DEPTH="${WOW_PROBE_MAX_DEPTH:-9}" \
  "${IMAGE}"
