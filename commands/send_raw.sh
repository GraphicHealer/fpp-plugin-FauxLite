#!/bin/bash
# FauxLite - Send Raw Command
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec /usr/bin/python3 "$DIR/lib/fauxlite.py" raw "${1:-}"
