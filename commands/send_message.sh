#!/bin/bash
# FauxLite - Send Message: writes text to a page and (optionally) runs it.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec /usr/bin/python3 "$DIR/lib/fauxlite.py" send \
    --text "${1:-}" --page "${2:-A}" --color "${3:-}" --font "${4:-}" \
    --size "${5:-}" --function "${6:-}" --display-mode "${7:-display}"
