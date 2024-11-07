#!/bin/bash

set -o pipefail

CURRENT_UID=$(id -u)
CURRENT_GID=$(id -g)

export WORKSPACE_ROOT=/opt/flare_bypasser/var/
export PYTHONPATH=$PYTHONPATH:/opt/flare_bypasser/extensions/

sudo -n find "$WORKSPACE_ROOT" -exec chown "$CURRENT_UID:$CURRENT_GID" {} \;
mkdir -p "$WORKSPACE_ROOT/log"

EXTENSION_MODULES=$(
  find /opt/flare_bypasser/extensions/ -type f -name '*.py' -not -name '.*' 2>/dev/null | \
    sed 's|^/opt/flare_bypasser/extensions/||' | \
    sed -r 's/[.]py$//' | \
    sed 's/$/:get_user_commands/')

EXTENSION_MODULES_PARAM=""

if [ "$EXTENSION_MODULES" != "" ]
then
  EXTENSION_MODULES_PARAM="--extensions $EXTENSION_MODULES"
fi

echo "Run server (extensions = $EXTENSION_MODULES)"

flare_bypass_server -b 0.0.0.0:8080 $EXTENSION_MODULES_PARAM 2>&1 | \
  tee "$WORKSPACE_ROOT/log/flare_bypass_server.log"
