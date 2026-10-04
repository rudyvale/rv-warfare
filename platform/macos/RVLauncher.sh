#!/bin/sh
set -eu
RV_CONTENTS="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
RV_JAVA="$RV_CONTENTS/runtime/Contents/Home/bin/java"
if ! "$RV_JAVA" -version >/dev/null 2>&1; then
  /usr/bin/osascript -e 'display dialog "RV uses Java 8 for Intel. On Apple Silicon, install Apple Rosetta 2, then open RV again." buttons {"OK"} default button "OK"'
  exit 1
fi
exec "$RV_JAVA" -Dfile.encoding=UTF-8 -jar "$RV_CONTENTS/Resources/rv-launcher.jar" --resources "$RV_CONTENTS/Resources"
