#!/bin/sh
set -eu
RV_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec "$RV_DIR/RV.app/Contents/MacOS/RVLauncher"
