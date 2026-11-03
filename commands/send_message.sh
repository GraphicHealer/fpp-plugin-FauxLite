#!/bin/bash
# FauxLite - Send Message: writes text to a page and (optionally) runs it.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
setsid /usr/bin/python3 "$DIR/lib/fauxlite.py" send \
    --text "${1:-}" --page "${2:-C}" --color "${3:-}" --font "${4:-}" \
    --size "${5:-}" --function "${6:-}" --display-mode "${7:-display}" </dev/null >/dev/null 2>&1 &
