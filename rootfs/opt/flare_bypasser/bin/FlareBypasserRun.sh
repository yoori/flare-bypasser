#!/bin/bash

CURRENT_UID=$(id -u)
CURRENT_GID=$(id -g)
CHROME_VERSION="${CHROME_VERSION:-130}"

export WORKSPACE_ROOT=/opt/flare_bypasser/var/
sudo -n find "$WORKSPACE_ROOT" -exec chown "$CURRENT_UID:$CURRENT_GID" {} \;
mkdir -p "$WORKSPACE_ROOT/log"

# Install chrome
sudo python3 /opt/flare_bypasser/bin/linux_chrome_installer.py \
  --version-prefix="$CHROME_VERSION" >"$WORKSPACE_ROOT/log/linux_chrome_installer.log" 2>&1 || \
  { echo "Chrome of required version '$CHROME_VERSION' not found" >&2 ; exit 1 ; }

flare_bypass_server -b 0.0.0.0:8080 >"$WORKSPACE_ROOT/log/flare_bypass_server.log" 2>&1
