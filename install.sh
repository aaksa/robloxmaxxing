#!/usr/bin/env bash
# install.sh - check requirements, then link (or copy) this folder into the Claude Code skills directory.
# Usage:  bash install.sh [--dir ~/.claude/skills/robloxmaxxing] [--copy] [--force]
# Needs Blender 5.x, Python 3 and Roblox Studio (with its MCP server enabled). Nothing is downloaded or installed.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$HOME/.claude/skills/robloxmaxxing"; COPY=0; FORCE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dir) TARGET="${2:?--dir needs a path}"; shift 2;;
    --copy) COPY=1; shift;;
    --force) FORCE=1; shift;;
    -h|--help) sed -n '2,4p' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done
MISSING=0; ok() { printf '  [ok]   %s\n' "$1"; }; bad() { printf '  [miss] %s\n' "$1"; MISSING=1; }; opt() { printf '  [opt]  %s\n' "$1"; }
echo "robloxmaxxing: checking requirements"
{ [ -x /Applications/Blender.app/Contents/MacOS/Blender ] || command -v blender >/dev/null; } && ok "Blender" || bad "Blender 5.x (builds and exports the assets)"
command -v python3 >/dev/null && ok "python3" || bad "Python 3.9+"
[ -x "${STUDIO_MCP:-/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP}" ] && ok "Roblox Studio MCP server" || bad "Roblox Studio with its MCP server (Assistant > Manage MCP Servers), or set STUDIO_MCP"
{ [ -n "${ROBLOX_API_KEY:-}" ] || security find-generic-password -s roblox-open-cloud >/dev/null 2>&1; } && ok "Open Cloud API key" || opt "no Open Cloud API key: preview and the 3D Importer still work; 'rbx.py upload' needs one"
[ "$MISSING" = 0 ] || { echo; echo "Install the missing requirements above, then run this again. Nothing was changed." >&2; exit 1; }
echo
if [ -e "$TARGET" ] || [ -L "$TARGET" ]; then
  [ "$FORCE" = 1 ] || { echo "$TARGET already exists. Re-run with --force to replace it." >&2; exit 1; }
  rm -rf "${TARGET:?}"
fi
mkdir -p "$(dirname "$TARGET")"
if [ "$COPY" = 1 ]; then
  mkdir -p "$TARGET"; (cd "$HERE" && tar --exclude=.git --exclude='*/out' --exclude=__pycache__ -cf - .) | (cd "$TARGET" && tar -xf -)
  echo "Copied to $TARGET"
else
  ln -s "$HERE" "$TARGET"; echo "Linked $TARGET -> $HERE"
fi
echo "Done. In Claude Code, ask for a Roblox asset built in Blender, or run /robloxmaxxing."
