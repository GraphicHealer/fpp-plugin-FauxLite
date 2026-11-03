#!/bin/bash
# FauxLite - Countdown To Time
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
setsid /usr/bin/python3 "$DIR/lib/fauxlite.py" countdown \
    --time "${1:-}" --date "${2:-}" --format "${3:-}" \
    --page "${4:-C}" --end-page "${5:-C}" --color "${6:-}" \
    --font "${7:-}" --size "${8:-}" --function "${9:-}" \
    --display-mode "${10:-display}" </dev/null >/dev/null 2>&1 &
