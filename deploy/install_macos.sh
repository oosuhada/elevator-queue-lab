#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-4174}"
REPLAY_ARTIFACT="${REPLAY_ARTIFACT:-$ROOT/evidence/public-demo-replay.json}"
LABEL="dev.oosu.elevator-queue-lab"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/elevator-queue-lab"
DOMAIN="${LAUNCHD_DOMAIN:-gui/$(id -u)}"

python_is_supported() {
  local candidate="$1"
  [ -x "$candidate" ] || return 1
  "$candidate" - <<'PY' >/dev/null 2>&1
import sys

raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
}

select_python() {
  local candidate
  local path_python=""

  if [ -n "${PYTHON_BIN:-}" ]; then
    if python_is_supported "$PYTHON_BIN"; then
      printf '%s\n' "$PYTHON_BIN"
      return 0
    fi
    echo "PYTHON_BIN must point to Python 3.11 or newer: $PYTHON_BIN" >&2
    return 1
  fi

  path_python="$(command -v python3 2>/dev/null || true)"
  for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 "$path_python"; do
    [ -n "$candidate" ] || continue
    if python_is_supported "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  echo "Elevator Queue Lab requires Python 3.11 or newer." >&2
  echo "Install a supported Python or set PYTHON_BIN explicitly." >&2
  return 1
}

PYTHON_BIN="$(select_python)"

if [ ! -f "$REPLAY_ARTIFACT" ]; then
  echo "Public replay artifact is missing: $REPLAY_ARTIFACT" >&2
  echo "Run: python scripts/generate_public_demo_replay.py" >&2
  exit 1
fi

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
REPLAY_XML="$(xml_escape "$REPLAY_ARTIFACT")"
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
    <string>--replay-artifact</string>
    <string>$REPLAY_XML</string>
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
BOOTSTRAPPED=false
for _ in {1..20}; do
  if launchctl bootstrap "$DOMAIN" "$PLIST" 2>/dev/null; then
    BOOTSTRAPPED=true
    break
  fi
  sleep 0.25
done
if [ "$BOOTSTRAPPED" != true ]; then
  echo "Unable to bootstrap $LABEL after waiting for launchd to release the old service." >&2
  launchctl bootstrap "$DOMAIN" "$PLIST"
  exit 1
fi
launchctl enable "$DOMAIN/$LABEL"
launchctl kickstart -k "$DOMAIN/$LABEL"

for _ in {1..240}; do
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
