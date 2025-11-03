#!/usr/bin/env bash
# Adjust python and project dir
PYTHON_BIN="/usr/bin/python3"
PROJECT_DIR="/absolute/path/to/lan_share"

cd "$PROJECT_DIR" || exit 1
# Start server in background
nohup "$PYTHON_BIN" server.py > lan_share_native.log 2>&1 &
# Reply with JSON (Native Messaging expects JSON on stdout)
printf '{"started": true}'
