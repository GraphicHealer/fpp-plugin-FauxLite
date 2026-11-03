#!/bin/bash
# FauxLite - Send Raw Command
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
setsid /usr/bin/python3 "$DIR/lib/fauxlite.py" raw "${1:-}" </dev/null >/dev/null 2>&1 &
