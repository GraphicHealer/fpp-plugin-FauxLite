#!/bin/bash
# FauxLite - Run Page
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
setsid /usr/bin/python3 "$DIR/lib/fauxlite.py" run --page "${1:-A}" </dev/null >/dev/null 2>&1 &
