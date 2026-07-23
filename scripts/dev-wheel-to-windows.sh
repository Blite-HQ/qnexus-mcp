#!/usr/bin/env bash
# Rebuild the wheel and drop it where the Windows-native MCP configs point.
#
# The Windows-side test setup (VS Code %APPDATA%\Code\User\mcp.json and Claude Desktop's
# claude_desktop_config.json -- Store builds keep it under
# AppData\Local\Packages\Claude_*\LocalCache\Roaming\Claude) runs the LOCAL build via:
#   uvx --from C:\Users\<user>\qnexus-mcp-dev\qnexus_mcp-<ver>-py3-none-any.whl qnexus-mcp
#
# uvx keys its cached environment on the wheel's content, so a rebuilt wheel is picked up
# automatically on the next launch (verified live: a changed wheel triggered a fresh install;
# the first launch after a rebuild takes ~1 min while the environment is recreated, later
# launches ~30 s). Do NOT add `uv cache clean` here: it is unnecessary and hangs on Windows
# file locks while any client still runs the old server. `--reinstall` is ignored by uvx.
#
# Run this from WSL after every change you want to test on Windows-native clients, then
# restart the MCP server in the client (Claude Desktop needs `taskkill /F /IM claude.exe`;
# closing the window leaves the old process alive). Override QNEXUS_MCP_WIN_DEV_DIR if your
# Windows username differs from $USER.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
dest="${QNEXUS_MCP_WIN_DEV_DIR:-/mnt/c/Users/$USER/qnexus-mcp-dev}"

cd "$repo"
uv build --wheel
mkdir -p "$dest"
cp dist/qnexus_mcp-*-py3-none-any.whl "$dest/"
echo "wheel copied -> $dest:"
ls -la "$dest"
