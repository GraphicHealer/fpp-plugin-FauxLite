#!/bin/bash
# FauxLite - Show Time
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
setsid /usr/bin/python3 "$DIR/lib/fauxlite.py" time --page "${1:-C}" </dev/null >/dev/null 2>&1 &
