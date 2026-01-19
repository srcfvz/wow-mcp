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

if [[ -z "${WOW_SCAN_ROOT_HOST:-}" ]]; then
  err "ERROR: WOW_SCAN_ROOT_HOST is not set."
  err "Set it in ${ENV_FILE} (recommended) or export it in your shell."
  exit 2
fi

ADDONS_DIR="${WOW_SCAN_ROOT_HOST}/Interface/AddOns"
if [[ ! -d "${ADDONS_DIR}" ]]; then
  err "ERROR: AddOns directory not found: ${ADDONS_DIR}"
  err "WOW_SCAN_ROOT_HOST should be the folder containing Interface/ and WTF/."
  exit 2
fi

SRC_ADDON_DIR="${SCRIPT_DIR}/addon"
if [[ ! -d "${SRC_ADDON_DIR}/WowMCP_State" ]] || [[ ! -d "${SRC_ADDON_DIR}/WowMCP_Cmd" ]]; then
  err "ERROR: Source addon folders missing under: ${SRC_ADDON_DIR}"
  exit 2
fi

copy_addon() {
  local name="$1"
  local src="${SRC_ADDON_DIR}/${name}"
  local dst="${ADDONS_DIR}/${name}"

  printf 'Installing %s -> %s\n' "${name}" "${dst}"
  mkdir -p "${dst}"

  if command -v rsync >/dev/null 2>&1; then
    rsync -a "${src}/" "${dst}/"
    return
  fi

  cp -a "${src}/." "${dst}/"
}

copy_addon "WowMCP_State"
copy_addon "WowMCP_Cmd"

printf '\nDone.\n'
printf 'In WoW: enable "WowMCP State" (and optionally "WowMCP Cmd"), then run /reload or logout to write SavedVariables.\n'
