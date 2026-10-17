#!/bin/sh
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
  exec python3 dashboard/launcher.py
fi
echo "Python 3 is required."
read -r _
exit 1
