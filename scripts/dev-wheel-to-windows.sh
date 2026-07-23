#!/usr/bin/env bash
# Rebuild the wheel and drop it where the Windows-native MCP configs point.
#
# The Windows-side test setup (VS Code %APPDATA%\Code\User\mcp.json and Claude Desktop
# %APPDATA%\Claude\claude_desktop_config.json) runs the LOCAL build via:
#   uvx --reinstall --from C:\Users\<user>\qnexus-mcp-dev\qnexus_mcp-<ver>-py3-none-any.whl qnexus-mcp
# (--reinstall makes every launch pick up the freshly copied wheel.)
#
# Run this from WSL after every change you want to test on Windows-native clients,
# then restart the MCP server in the client. Override the destination with
# QNEXUS_MCP_WIN_DEV_DIR if your Windows username differs from $USER.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
dest="${QNEXUS_MCP_WIN_DEV_DIR:-/mnt/c/Users/$USER/qnexus-mcp-dev}"

cd "$repo"
uv build --wheel
mkdir -p "$dest"
cp dist/qnexus_mcp-*-py3-none-any.whl "$dest/"
echo "wheel copied -> $dest:"
ls -la "$dest"
