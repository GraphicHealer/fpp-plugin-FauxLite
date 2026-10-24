#!/bin/bash
# FauxLite - Countdown To Time
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec /usr/bin/python3 "$DIR/lib/fauxlite.py" countdown \
    --time "${1:-}" --date "${2:-}" --format "${3:-}" \
    --page "${4:-A}" --end-page "${5:-A}" --color "${6:-}" \
    --font "${7:-}" --size "${8:-}" --function "${9:-}" \
    --display-mode "${10:-display}"
