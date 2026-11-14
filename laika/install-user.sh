#!/usr/bin/env bash
set -euo pipefail

# User-space L.A.I.K.A. bootstrap for Linux Mint x86_64.
# No sudo, no system package installation, no global library changes.

VERSION="v0.20.1"
ASSET="fono-v0.20.1-x86_64"
URL="https://github.com/bogdanr/fono/releases/download/v0.20.1/fono-v0.20.1-x86_64"
SHA256="125acaa13eefeb66f88c23e947031bcf86b6b35b98cc682d3447573addb9cda2"
MODEL="qwen2.5:1.5b"

[[ "$(uname -m)" == "x86_64" ]] || { echo "This build is for x86_64 Linux."; exit 1; }
command -v curl >/dev/null || { echo "curl is required."; exit 1; }
command -v sha256sum >/dev/null || { echo "sha256sum is required."; exit 1; }
command -v python3 >/dev/null || { echo "Python 3 is required."; exit 1; }

PYTHON="$(command -v python3)"
"$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
  || { echo "Python 3.11+ is required for the local tools server."; exit 1; }

OLLAMA=""
if command -v ollama >/dev/null 2>&1; then
  OLLAMA="$(command -v ollama)"
elif [[ -x "$HOME/.local/bin/ollama" ]]; then
  OLLAMA="$HOME/.local/bin/ollama"
fi
[[ -n "$OLLAMA" ]] || { echo "Ollama was not found; leaving your existing setup untouched."; exit 1; }

APP_BIN="$HOME/.local/bin/fono"
APP_DATA="$HOME/.local/share/laika"
APP_STATE="$HOME/.local/state/laika"
CONFIG_DIR="$HOME/.config/fono"
AUTOSTART="$HOME/.config/autostart"
mkdir -p "$HOME/.local/bin" "$APP_DATA" "$APP_STATE" "$CONFIG_DIR" "$AUTOSTART"

# Start the existing local Ollama service only if it is not already answering.
if ! curl -fsS --max-time 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
  nohup "$OLLAMA" serve >>"$APP_STATE/ollama.log" 2>&1 </dev/null &
  ready=0
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then ready=1; break; fi
    sleep 1
  done
  [[ "$ready" -eq 1 ]] || { echo "Ollama did not start. See $APP_STATE/ollama.log"; exit 1; }
fi

"$OLLAMA" list | awk 'NR > 1 {print $1}' | grep -Fxq "$MODEL" \
  || { echo "Required local model $MODEL is not installed. No model was downloaded."; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
echo "Downloading Fono $VERSION CPU build..."
curl -fL --retry 3 --connect-timeout 15 "$URL" -o "$tmp/$ASSET"
printf '%s  %s\n' "$SHA256" "$tmp/$ASSET" | sha256sum -c -

install -m 755 "$tmp/$ASSET" "$APP_BIN"
install -m 644 "$(dirname "$0")/mcp_server.py" "$APP_DATA/mcp_server.py"

# Preserve an existing Fono config before applying the L.A.I.K.A. profile.
if [[ -f "$CONFIG_DIR/config.toml" ]]; then
  cp -n "$CONFIG_DIR/config.toml" "$CONFIG_DIR/config.toml.before-laika"
fi
cat >"$CONFIG_DIR/config.toml" <<EOF
[assistant]
enabled = true
backend = "network"

[assistant.network]
url = "http://127.0.0.1:11434/v1/chat/completions"
model = "$MODEL"

[assistant.tools]
enabled = true

[[assistant.tools.mcp]]
name = "LAIKA Local Tools"
url = "http://127.0.0.1:8765/mcp"
EOF
chmod 600 "$CONFIG_DIR/config.toml"

# Prefer a per-user systemd service. Fall back to XDG autostart if the user
# session bus is unavailable; both paths remain inside the home directory.
if command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
  UNIT_DIR="$HOME/.config/systemd/user"
  mkdir -p "$UNIT_DIR"
  cat >"$UNIT_DIR/laika-mcp.service" <<EOF
[Unit]
Description=L.A.I.K.A. local tools (MCP)
After=default.target

[Service]
Type=simple
ExecStart=$PYTHON $APP_DATA/mcp_server.py
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
ProtectSystem=full
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable --now laika-mcp.service
else
  cat >"$AUTOSTART/laika-mcp.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=L.A.I.K.A. Local Tools
Comment=Start the local L.A.I.K.A. tools service
Exec=$PYTHON $APP_DATA/mcp_server.py
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
  if ! curl -fsS --max-time 1 http://127.0.0.1:8765/health >/dev/null 2>&1; then
    nohup "$PYTHON" "$APP_DATA/mcp_server.py" >>"$APP_STATE/mcp.log" 2>&1 </dev/null &
  fi
fi

# Start Fono in the background. The config above points it at local Ollama.
if ! pgrep -x fono >/dev/null 2>&1; then
  nohup "$APP_BIN" >>"$APP_STATE/fono.log" 2>&1 </dev/null &
fi

cat >"$AUTOSTART/laika-fono.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=L.A.I.K.A. Voice Assistant
Comment=Start the local Fono voice interface for L.A.I.K.A.
Exec=$APP_BIN
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

echo
echo "L.A.I.K.A. voice foundation installed for this user."
echo "Fono: $APP_BIN"
echo "Local tools: http://127.0.0.1:8765/health"
echo "Ollama model: $MODEL"
echo "Logs: $APP_STATE/"
echo "No administrator access or system packages were used."
