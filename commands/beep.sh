#!/bin/bash
# FauxLite - Beep
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec /usr/bin/python3 "$DIR/lib/fauxlite.py" beep --count "${1:-1}"
