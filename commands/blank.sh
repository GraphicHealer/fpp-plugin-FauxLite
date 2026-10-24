#!/bin/bash
# FauxLite - Blank Display
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec /usr/bin/python3 "$DIR/lib/fauxlite.py" blank --page "${1:-A}"
