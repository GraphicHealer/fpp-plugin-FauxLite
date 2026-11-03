#!/bin/bash
# FauxLite - One-Shot Message: temporary message on reserved pages Y/Z.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BEEP=""
[ "${7:-no}" = "yes" ] && BEEP="--beep"
setsid /usr/bin/python3 "$DIR/lib/fauxlite.py" oneshot \
    --text "${1:-}" --repeat "${2:-1}" --color "${3:-}" --font "${4:-}" \
    --size "${5:-}" --function "${6:-}" $BEEP </dev/null >/dev/null 2>&1 &
