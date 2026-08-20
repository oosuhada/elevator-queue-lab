#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
PORT="${PORT:-4174}"
LABEL="dev.oosu.elevator-queue-lab"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/elevator-queue-lab"
DOMAIN="${LAUNCHD_DOMAIN:-gui/$(id -u)}"

mkdir -p "$(dirname "$PLIST")" "$LOG_DIR"

xml_escape() {
  "$PYTHON_BIN" - "$1" <<'PY'
import html
import sys
print(html.escape(sys.argv[1], quote=True))
PY
}

ROOT_XML="$(xml_escape "$ROOT")"
PYTHON_XML="$(xml_escape "$PYTHON_BIN")"
PORT_XML="$(xml_escape "$PORT")"
OUT_XML="$(xml_escape "$LOG_DIR/server.out.log")"
ERR_XML="$(xml_escape "$LOG_DIR/server.err.log")"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_XML</string>
    <string>-u</string>
    <string>-m</string>
    <string>app.server</string>
    <string>--host</string>
    <string>127.0.0.1</string>
    <string>--port</string>
    <string>$PORT_XML</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$ROOT_XML</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>5</integer>
  <key>StandardOutPath</key>
  <string>$OUT_XML</string>
  <key>StandardErrorPath</key>
  <string>$ERR_XML</string>
</dict>
</plist>
EOF

plutil -lint "$PLIST"
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl enable "$DOMAIN/$LABEL"
launchctl kickstart -k "$DOMAIN/$LABEL"

for _ in {1..40}; do
  if curl --fail --silent "http://127.0.0.1:$PORT/api/health" >/dev/null; then
    echo "Elevator Queue Lab launchd service is healthy."
    echo "Local URL: http://127.0.0.1:$PORT/"
    exit 0
  fi
  sleep 0.25
done

echo "Service did not become healthy; recent stderr follows:" >&2
tail -n 80 "$LOG_DIR/server.err.log" >&2 || true
exit 1
